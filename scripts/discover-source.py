#!/usr/bin/env python3
"""Discover the newest verified mirrored Realtek r8125 source archive."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_SOURCES = [
    {
        "name": "openwrt",
        "repo": "openwrt/rtl8125",
        "asset_pattern": r"r8125-[0-9][0-9.]*\.tar\.(bz2|gz|xz)$",
    },
    {
        "name": "danixland",
        "repo": "danixland/r8125",
        "asset_pattern": r"r8125-[0-9][0-9.]*\.tar\.(bz2|gz|xz)$",
    },
]

REALTEK_DOWNLOAD_LIST_URL = "https://www.realtek.com/Download/List?cate_id=584"
REALTEK_DOWNLOAD_API_URL = "https://www.realtek.com/Download/ListAllDownloadItem?cate_id=584"
SHA256_DIGEST_RE = re.compile(r"sha256:([0-9a-f]{64})", re.IGNORECASE)


@dataclass(frozen=True)
class SourceAsset:
    source: str
    repo: str
    release_tag: str
    release_url: str
    version: str
    asset_name: str
    asset_url: str
    digest: str
    prerelease: bool


@dataclass(frozen=True)
class OfficialRelease:
    version: str
    asset_name: str
    download_id: str
    update_time: str


def github_json(url: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "r8125-driver-packages",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc.code} {url}") from exc


def public_json(url: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "r8125-driver-packages"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"public JSON request failed: {exc.code} {url}") from exc


def parse_sources(config_path: str | None) -> list[dict[str, str]]:
    if not config_path or not os.path.exists(config_path):
        return DEFAULT_SOURCES

    # Keep this intentionally narrow so the project does not need PyYAML.
    with open(config_path, encoding="utf-8") as handle:
        text = handle.read()
    items: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if current:
                items.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if stripped:
                key, value = stripped.split(":", 1)
                current[key.strip()] = value.strip().strip("'\"")
        elif current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip().strip("'\"")
    if current:
        items.append(current)

    return items or DEFAULT_SOURCES


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def asset_version(asset_name: str) -> str | None:
    match = re.search(r"r8125-([0-9][0-9.]*)\.tar\.(?:bz2|gz|xz)$", asset_name)
    return match.group(1) if match else None


def parse_official_release(payload: Any) -> OfficialRelease:
    if not isinstance(payload, dict) or payload.get("Pass") is not True:
        raise ValueError("Realtek response did not report success")
    data = payload.get("Data") if isinstance(payload, dict) else None
    download_items = data.get("DownloadItems") if isinstance(data, dict) else None
    if not isinstance(download_items, dict):
        raise ValueError("Realtek response has no DownloadItems object")

    candidates: list[OfficialRelease] = []
    for items in download_items.values():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("Name", ""))
            version = asset_version(name)
            if not version:
                continue
            declared_version = str(item.get("Version", ""))
            if declared_version and version_key(declared_version) != version_key(version):
                continue
            candidates.append(
                OfficialRelease(
                    version=version,
                    asset_name=name,
                    download_id=str(item.get("DownloadId", "")),
                    update_time=str(item.get("UpdateTime", "")),
                )
            )

    if not candidates:
        raise ValueError("Realtek response has no r8125 source archive")
    return max(candidates, key=lambda item: version_key(item.version))


def official_release() -> OfficialRelease:
    return parse_official_release(public_json(REALTEK_DOWNLOAD_API_URL))


def candidates_for_source(source: dict[str, str]) -> list[SourceAsset]:
    repo = source["repo"]
    pattern = re.compile(source.get("asset_pattern") or DEFAULT_SOURCES[0]["asset_pattern"])
    releases = github_json(f"https://api.github.com/repos/{repo}/releases?per_page=20")
    candidates: list[SourceAsset] = []

    for release in releases:
        if release.get("draft"):
            continue
        if release.get("prerelease"):
            continue
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if not pattern.search(name):
                continue
            version = asset_version(name)
            if not version:
                continue
            digest_match = SHA256_DIGEST_RE.fullmatch(str(asset.get("digest", "")))
            if not digest_match:
                continue
            candidates.append(
                SourceAsset(
                    source=source["name"],
                    repo=repo,
                    release_tag=release["tag_name"],
                    release_url=release["html_url"],
                    version=version,
                    asset_name=name,
                    asset_url=asset["browser_download_url"],
                    digest=f"sha256:{digest_match.group(1).lower()}",
                    prerelease=bool(release.get("prerelease")),
                )
            )
    return candidates


def select_latest_candidate(candidates: list[SourceAsset], official_version: str) -> SourceAsset:
    official_key = version_key(official_version)
    eligible = [item for item in candidates if version_key(item.version) <= official_key]
    if not eligible:
        raise ValueError(f"no mirrored source is at or below Realtek {official_version}")
    # max() keeps the first configured source when versions are equal.
    return max(eligible, key=lambda item: version_key(item.version))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/sources.yml")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        official = official_release()
    except Exception as exc:  # noqa: BLE001 - fail closed when the authority is unavailable.
        print(f"realtek: {exc}", file=sys.stderr)
        return 1

    all_candidates: list[SourceAsset] = []
    errors: list[str] = []
    for source in parse_sources(args.config):
        try:
            all_candidates.extend(candidates_for_source(source))
        except Exception as exc:  # noqa: BLE001 - keep source fallback resilient.
            errors.append(f"{source.get('name', source.get('repo', 'unknown'))}: {exc}")

    if not all_candidates:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    for error in errors:
        print(error, file=sys.stderr)
    rejected = [
        item for item in all_candidates if version_key(item.version) > version_key(official.version)
    ]
    for item in rejected:
        print(
            f"ignoring {item.repo} {item.version}: newer than Realtek {official.version}",
            file=sys.stderr,
        )
    try:
        selected = select_latest_candidate(all_candidates, official.version)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    payload = {
        "source": selected.source,
        "repo": selected.repo,
        "release_tag": selected.release_tag,
        "release_url": selected.release_url,
        "driver_version": selected.version,
        "asset_name": selected.asset_name,
        "asset_url": selected.asset_url,
        "digest": selected.digest,
        "prerelease": selected.prerelease,
        "official_driver_version": official.version,
        "official_asset_name": official.asset_name,
        "official_download_id": official.download_id,
        "official_update_time": official.update_time,
        "official_source_url": REALTEK_DOWNLOAD_LIST_URL,
    }
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
