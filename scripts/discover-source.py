#!/usr/bin/env python3
"""Discover the newest mirrored Realtek r8125 source archive."""

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
        "name": "devome",
        "repo": "devome/r8125-dkms",
        "asset_pattern": r"r8125-[0-9][0-9.]*\.tar\.(bz2|gz|xz)$",
    },
]


@dataclass(frozen=True)
class SourceAsset:
    source: str
    repo: str
    release_tag: str
    release_url: str
    version: str
    asset_name: str
    asset_url: str
    digest: str | None
    prerelease: bool


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


def parse_sources(config_path: str | None) -> list[dict[str, str]]:
    if not config_path or not os.path.exists(config_path):
        return DEFAULT_SOURCES

    # Keep this intentionally narrow so the project does not need PyYAML.
    text = open(config_path, encoding="utf-8").read()
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


def candidates_for_source(source: dict[str, str], include_prereleases: bool) -> list[SourceAsset]:
    repo = source["repo"]
    pattern = re.compile(source.get("asset_pattern") or DEFAULT_SOURCES[0]["asset_pattern"])
    releases = github_json(f"https://api.github.com/repos/{repo}/releases?per_page=20")
    candidates: list[SourceAsset] = []

    for release in releases:
        if release.get("draft"):
            continue
        if release.get("prerelease") and not include_prereleases:
            continue
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if not pattern.search(name):
                continue
            version = asset_version(name)
            if not version:
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
                    digest=asset.get("digest"),
                    prerelease=bool(release.get("prerelease")),
                )
            )
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/sources.yml")
    parser.add_argument("--include-prereleases", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    all_candidates: list[SourceAsset] = []
    errors: list[str] = []
    for source in parse_sources(args.config):
        try:
            all_candidates.extend(candidates_for_source(source, args.include_prereleases))
        except Exception as exc:  # noqa: BLE001 - keep source fallback resilient.
            errors.append(f"{source.get('name', source.get('repo', 'unknown'))}: {exc}")

    if not all_candidates:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    selected = max(all_candidates, key=lambda item: version_key(item.version))
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
    }
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
