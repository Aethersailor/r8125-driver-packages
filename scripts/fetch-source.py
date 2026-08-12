#!/usr/bin/env python3
"""Download a discovered r8125 source archive and emit metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, path: str) -> None:
    headers = {"User-Agent": "r8125-driver-packages"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as response, open(path, "wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)


def normalize_sha256(value: str) -> str:
    normalized = value.lower()
    if normalized.startswith("sha256:"):
        normalized = normalized.split(":", 1)[1]
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise ValueError("source metadata must contain a valid SHA256 digest")
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", help="Metadata JSON from discover-source.py")
    parser.add_argument("--url", help="Explicit source URL")
    parser.add_argument("--version", help="Driver version for explicit URL")
    parser.add_argument("--sha256", help="Expected SHA256 for an explicit source URL")
    parser.add_argument("--out-dir", default="downloads")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.metadata:
        with open(args.metadata, encoding="utf-8") as handle:
            metadata = json.load(handle)
    elif args.url and args.version and args.sha256:
        name = os.path.basename(args.url)
        metadata = {
            "source": "manual",
            "repo": None,
            "release_tag": None,
            "release_url": None,
            "driver_version": args.version,
            "asset_name": name,
            "asset_url": args.url,
            "digest": f"sha256:{normalize_sha256(args.sha256)}",
            "prerelease": False,
        }
    elif args.url or args.version or args.sha256:
        parser.error("--url, --version, and --sha256 must be used together")
    else:
        result = subprocess.run(
            [sys.executable, "scripts/discover-source.py"],
            check=True,
            capture_output=True,
            text=True,
        )
        metadata = json.loads(result.stdout)

    expected_sha256 = normalize_sha256(str(metadata.get("digest", "")))
    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, metadata["asset_name"])
    if not os.path.exists(out_path):
        download(metadata["asset_url"], out_path)

    actual_sha256 = sha256_file(out_path)
    if expected_sha256 != actual_sha256:
        raise RuntimeError(f"sha256 mismatch for {out_path}: {actual_sha256} != {expected_sha256}")

    metadata["source_path"] = out_path
    metadata["source_sha256"] = actual_sha256
    print(json.dumps(metadata, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
