#!/usr/bin/env python3
"""Generate bilingual release notes for a packaged r8125 driver."""

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
    build_options_text = ", ".join(f"`{option}`" for option in build_options)

    print(f"## r8125-dkms {args.package_version}")
    print()
    print("### 中文")
    print()
    print(f"- 驱动版本：`{metadata['driver_version']}`")
    print(f"- Realtek 官方确认版本：`{metadata['official_driver_version']}`")
    print(f"- 源码来源：`{metadata['source']}` / `{metadata.get('repo')}`")
    print(f"- 源码归档：`{metadata['asset_name']}`")
    print(f"- 源码 SHA256：`{metadata['source_sha256']}`")
    print(f"- DKMS 构建参数：{build_options_text}")
    print()
    print("这是一个 DKMS 源码包。安装到 Debian 或 Proxmox VE 主机后，内核模块会在目标系统上根据本机内核头文件编译。")
    print()
    print("### English")
    print()
    print(f"- Driver version: `{metadata['driver_version']}`")
    print(f"- Realtek-confirmed version: `{metadata['official_driver_version']}`")
    print(f"- Source: `{metadata['source']}` / `{metadata.get('repo')}`")
    print(f"- Source archive: `{metadata['asset_name']}`")
    print(f"- Source SHA256: `{metadata['source_sha256']}`")
    print(f"- DKMS build options: {build_options_text}")
    print()
    print("This is a DKMS source package. The kernel module is built on the target Debian or Proxmox VE host during package installation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
