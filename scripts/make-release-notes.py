#!/usr/bin/env python3
"""Generate concise release notes for a packaged r8125 driver."""

from __future__ import annotations

import argparse
import json


def read_build_options(path: str) -> list[str]:
    options: list[str] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                options.append(stripped)
    return options


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--package-version", required=True)
    parser.add_argument("--build-options", default="config/build-options.env")
    args = parser.parse_args()

    with open(args.metadata, encoding="utf-8") as handle:
        metadata = json.load(handle)
    build_options = read_build_options(args.build_options)

    print(f"## r8125-dkms {args.package_version}")
    print()
    print(f"- Driver version: `{metadata['driver_version']}`")
    print(f"- Source: `{metadata['source']}` / `{metadata.get('repo')}`")
    print(f"- Source asset: `{metadata['asset_name']}`")
    print(f"- Source SHA256: `{metadata['source_sha256']}`")
    print("- DKMS build options: " + ", ".join(f"`{option}`" for option in build_options))
    print()
    print("This is a DKMS source package. The kernel module is built on the target Debian or Proxmox VE host during package installation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
