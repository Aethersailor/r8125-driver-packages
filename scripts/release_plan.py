#!/usr/bin/env python3
"""Plan an r8125 package release from upstream and repository state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any


PACKAGE_RECIPE_PATHS = (
    "LICENSE",
    "config/build-options.env",
    "packaging/debian",
    "scripts/build-deb.sh",
)


@dataclass(frozen=True)
class ExistingRelease:
    pkgrel: int
    tag: str
    target_commitish: str
    source_sha256: str | None = None


@dataclass(frozen=True)
class ReleaseDecision:
    driver_version: str
    pkgrel: int
    package_version: str
    tag: str
    should_release: bool
    replace_existing: bool
    reason: str


def github_json(url: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "r8125-driver-packages",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc.code} {url}") from exc


def public_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "r8125-driver-packages"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Release asset request failed: {exc.code} {url}") from exc


def validate_driver_version(version: str) -> str:
    if not re.fullmatch(r"[0-9][0-9.]*", version):
        raise ValueError(f"invalid driver version: {version!r}")
    return version


def parse_pkgrel(value: str) -> int:
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise ValueError(f"pkgrel must be a positive integer: {value!r}")
    return int(value)


def recipe_paths(driver_version: str) -> tuple[str, ...]:
    return (*PACKAGE_RECIPE_PATHS, f"patches/{driver_version}")


def git_command(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        check=check,
        capture_output=True,
    )


def git_ref_exists(ref: str) -> bool:
    result = git_command("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
    return result.returncode == 0


def recipe_changed(base_ref: str, head_ref: str, driver_version: str) -> bool:
    result = git_command(
        "diff",
        "--quiet",
        base_ref,
        head_ref,
        "--",
        *recipe_paths(driver_version),
        check=False,
    )
    if result.returncode not in (0, 1):
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git diff failed for {base_ref}..{head_ref}: {stderr}")
    return result.returncode == 1


def recipe_sha256(ref: str, driver_version: str) -> str:
    result = git_command(
        "ls-tree",
        "-r",
        "--full-tree",
        ref,
        "--",
        *recipe_paths(driver_version),
    )
    if not result.stdout:
        raise RuntimeError(f"package recipe is empty at {ref}")
    return hashlib.sha256(result.stdout).hexdigest()


def matching_releases(repository: str, driver_version: str) -> tuple[list[ExistingRelease], dict[str, dict[str, Any]]]:
    payload = github_json(f"https://api.github.com/repos/{repository}/releases?per_page=100")
    pattern = re.compile(rf"^v{re.escape(driver_version)}-([1-9][0-9]*)$")
    releases: list[ExistingRelease] = []
    raw_by_tag: dict[str, dict[str, Any]] = {}
    for item in payload:
        match = pattern.fullmatch(item.get("tag_name", ""))
        if not match:
            continue
        tag = item["tag_name"]
        releases.append(
            ExistingRelease(
                pkgrel=int(match.group(1)),
                tag=tag,
                target_commitish=item.get("target_commitish", ""),
            )
        )
        raw_by_tag[tag] = item
    return sorted(releases, key=lambda item: item.pkgrel), raw_by_tag


def release_source_sha256(release: ExistingRelease, raw_release: dict[str, Any]) -> str:
    provenance_asset = next(
        (asset for asset in raw_release.get("assets", []) if asset.get("name") == "provenance.json"),
        None,
    )
    if provenance_asset is None:
        raise RuntimeError(f"{release.tag} has no provenance.json asset")
    provenance = public_json(provenance_asset["browser_download_url"])
    source_sha256 = str(provenance.get("source_sha256", "")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise RuntimeError(f"{release.tag} provenance has no valid source_sha256")
    return source_sha256


def choose_release(
    driver_version: str,
    current_source_sha256: str,
    releases: list[ExistingRelease],
    *,
    has_recipe_changes: bool = False,
    manual_pkgrel: str = "",
    force: bool = False,
) -> ReleaseDecision:
    releases_by_pkgrel = {release.pkgrel: release for release in releases}

    if manual_pkgrel:
        pkgrel = parse_pkgrel(manual_pkgrel)
        exists = pkgrel in releases_by_pkgrel
        if exists and not force:
            should_release = False
            replace_existing = False
            reason = "manual-tag-already-exists"
        else:
            should_release = True
            replace_existing = exists and force
            reason = "forced-rebuild" if replace_existing else "manual-package-revision"
    elif releases:
        latest = max(releases, key=lambda item: item.pkgrel)
        if force:
            pkgrel = latest.pkgrel
            should_release = True
            replace_existing = True
            reason = "forced-rebuild"
        else:
            if latest.source_sha256 is None:
                raise ValueError("latest release is missing source identity")
            source_changed = latest.source_sha256 != current_source_sha256
            if source_changed or has_recipe_changes:
                pkgrel = latest.pkgrel + 1
                should_release = True
                replace_existing = False
                if source_changed and has_recipe_changes:
                    reason = "source-and-package-recipe-changed"
                elif source_changed:
                    reason = "source-asset-changed"
                else:
                    reason = "package-recipe-changed"
            else:
                pkgrel = latest.pkgrel
                should_release = False
                replace_existing = False
                reason = "source-and-package-recipe-unchanged"
    else:
        pkgrel = 1
        should_release = True
        replace_existing = False
        reason = "new-driver-version"

    package_version = f"{driver_version}-{pkgrel}"
    return ReleaseDecision(
        driver_version=driver_version,
        pkgrel=pkgrel,
        package_version=package_version,
        tag=f"v{package_version}",
        should_release=should_release,
        replace_existing=replace_existing,
        reason=reason,
    )


def write_github_output(path: str, payload: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in payload.items():
            if isinstance(value, bool):
                value = str(value).lower()
            handle.write(f"{key}={value}\n")


def write_summary(path: str, payload: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("### Debian release decision\n\n")
        handle.write(f"- Driver version: `{payload['driver_version']}`\n")
        handle.write(f"- Source SHA256: `{payload['source_sha256']}`\n")
        handle.write(f"- Package recipe SHA256: `{payload['recipe_sha256']}`\n")
        handle.write(f"- Planned tag: `{payload['tag']}`\n")
        handle.write(f"- Publish: `{str(payload['should_release']).lower()}`\n")
        handle.write(f"- Reason: `{payload['reason']}`\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--head-sha", default=os.environ.get("GITHUB_SHA", "HEAD"))
    parser.add_argument("--pkgrel", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--github-output")
    parser.add_argument("--summary")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.metadata == "-":
        metadata = json.load(sys.stdin)
    else:
        with open(args.metadata, encoding="utf-8") as handle:
            metadata = json.load(handle)
    driver_version = validate_driver_version(str(metadata["driver_version"]))
    current_source_sha256 = str(metadata.get("source_sha256", "")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", current_source_sha256):
        raise ValueError("metadata must contain a valid source_sha256")
    if not git_ref_exists(args.head_sha):
        raise RuntimeError(f"head commit is not available locally: {args.head_sha}")

    releases, raw_by_tag = matching_releases(args.repository, driver_version)
    has_recipe_changes = False
    if releases and not args.pkgrel and not args.force:
        latest = releases[-1]
        if not git_ref_exists(latest.tag):
            raise RuntimeError(f"release tag is not available locally: {latest.tag}")
        source_sha256 = release_source_sha256(latest, raw_by_tag[latest.tag])
        releases[-1] = ExistingRelease(
            pkgrel=latest.pkgrel,
            tag=latest.tag,
            target_commitish=latest.target_commitish,
            source_sha256=source_sha256,
        )
        has_recipe_changes = recipe_changed(latest.tag, args.head_sha, driver_version)

    decision = choose_release(
        driver_version,
        current_source_sha256,
        releases,
        has_recipe_changes=has_recipe_changes,
        manual_pkgrel=args.pkgrel,
        force=args.force,
    )
    release_tags = {release.tag for release in releases}
    if decision.should_release and decision.tag not in release_tags and git_ref_exists(decision.tag):
        raise RuntimeError(f"tag exists without a matching GitHub release: {decision.tag}")

    payload = asdict(decision)
    payload["source_sha256"] = current_source_sha256
    payload["recipe_sha256"] = recipe_sha256(args.head_sha, driver_version)
    if args.github_output:
        write_github_output(args.github_output, payload)
    if args.summary:
        write_summary(args.summary, payload)
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
