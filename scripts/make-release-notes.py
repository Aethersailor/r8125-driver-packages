#!/usr/bin/env python3
"""Generate bilingual release notes for a packaged r8125 driver."""

from __future__ import annotations

import argparse
import json
import re
from typing import Any
from urllib.parse import quote


def read_build_options(path: str) -> list[str]:
    options: list[str] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                options.append(stripped)
    return options


def validate_repository(repository: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError(f"invalid GitHub repository: {repository!r}")
    return repository


def validate_package_version(package_version: str) -> str:
    if not re.fullmatch(r"[0-9][0-9.]*-[1-9][0-9]*", package_version):
        raise ValueError(f"invalid package version: {package_version!r}")
    return package_version


def render_release_notes(
    metadata: dict[str, Any],
    package_version: str,
    repository: str,
    build_options: list[str],
) -> str:
    repository = validate_repository(repository)
    package_version = validate_package_version(package_version)
    tag = f"v{package_version}"
    package_asset = f"r8125-dkms_{package_version}_all.deb"
    release_base = f"https://github.com/{repository}/releases/download/{quote(tag)}"
    package_url = f"{release_base}/{quote(package_asset)}"
    source_url = f"{release_base}/{quote(str(metadata['asset_name']))}"
    readme_zh_url = (
        f"https://github.com/{repository}/blob/{quote(tag)}/README.md#"
        f"{quote('安装')}"
    )
    readme_en_url = (
        f"https://github.com/{repository}/blob/{quote(tag)}/README_EN.md#installation"
    )
    build_options_text = ", ".join(f"`{option}`" for option in build_options)

    lines = [
        f"## r8125-dkms {package_version}",
        "",
        "> [!IMPORTANT]",
        f"> **普通用户只需下载并安装 [`{package_asset}`]({package_url})。**",
        "> 页面底部由 GitHub 自动生成的 `Source code (zip)` 和 `Source code (tar.gz)` "
        "是仓库快照，不是 DKMS 安装包。",
        "",
        "### 中文",
        "",
        "#### 下载与安装",
        "",
        "这个 `.deb` 是可直接安装的 Debian DKMS 软件包。包内包含驱动源码，不包含预编译的内核模块；安装时，DKMS 会根据目标主机的内核头文件编译 `r8125.ko`。",
        "",
        f"1. 按照 [README 安装说明]({readme_zh_url})，为当前内核安装匹配的 headers。",
        f"2. 下载 [`{package_asset}`]({package_url})。",
        "3. 在下载目录中运行：",
        "",
        "```sh",
        f"sudo apt install ./{package_asset}",
        "```",
        "",
        "#### 发布信息",
        "",
        f"- 驱动版本：`{metadata['driver_version']}`",
        f"- Realtek 官方确认版本：`{metadata['official_driver_version']}`",
        f"- 源码来源：`{metadata['source']}` / `{metadata.get('repo')}`",
        f"- 源码归档：[`{metadata['asset_name']}`]({source_url})",
        f"- 源码 SHA256：`{metadata['source_sha256']}`",
        f"- DKMS 构建参数：{build_options_text}",
        "",
        "#### 附件说明",
        "",
        "| 文件 | 用途 | 安装是否需要 |",
        "| --- | --- | --- |",
        f"| `{package_asset}` | Debian DKMS 安装包 | 是 |",
        f"| `{metadata['asset_name']}` | 已校验的上游驱动源码归档 | 否 |",
        "| `SHA256SUMS` | 发布附件的 SHA256 校验值 | 否 |",
        "| `provenance.json` | 源码、构建参数、提交和工作流运行信息，供审计与追溯 | 否 |",
        "| `release-notes.md` | 自动发布过程保存的说明文件 | 否 |",
        "| `Source code (zip)` / `Source code (tar.gz)` | GitHub 自动生成的仓库快照 | 否 |",
        "",
        "### English",
        "",
        "> [!IMPORTANT]",
        f"> **Most users only need to download and install [`{package_asset}`]({package_url}).**",
        "> The automatically generated `Source code (zip)` and `Source code (tar.gz)` files are repository snapshots, not DKMS packages.",
        "",
        "#### Download and install",
        "",
        "The `.deb` is an installable Debian DKMS package. It contains driver source rather than a prebuilt kernel module; DKMS compiles `r8125.ko` against the target host's kernel headers during installation.",
        "",
        f"1. Follow the [README installation guide]({readme_en_url}) to install headers matching the current kernel.",
        f"2. Download [`{package_asset}`]({package_url}).",
        "3. Run the following command from the download directory:",
        "",
        "```sh",
        f"sudo apt install ./{package_asset}",
        "```",
        "",
        "#### Release information",
        "",
        f"- Driver version: `{metadata['driver_version']}`",
        f"- Realtek-confirmed version: `{metadata['official_driver_version']}`",
        f"- Source: `{metadata['source']}` / `{metadata.get('repo')}`",
        f"- Source archive: [`{metadata['asset_name']}`]({source_url})",
        f"- Source SHA256: `{metadata['source_sha256']}`",
        f"- DKMS build options: {build_options_text}",
        "",
        "#### Asset guide",
        "",
        "| File | Purpose | Required for installation |",
        "| --- | --- | --- |",
        f"| `{package_asset}` | Debian DKMS package | Yes |",
        f"| `{metadata['asset_name']}` | Verified upstream driver source archive | No |",
        "| `SHA256SUMS` | SHA256 checksums for release assets | No |",
        "| `provenance.json` | Source, build options, commit, and workflow-run provenance for auditing | No |",
        "| `release-notes.md` | Release notes saved by the publication workflow | No |",
        "| `Source code (zip)` / `Source code (tar.gz)` | Repository snapshots generated by GitHub | No |",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--package-version", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--build-options", default="config/build-options.env")
    args = parser.parse_args()

    with open(args.metadata, encoding="utf-8") as handle:
        metadata = json.load(handle)
    build_options = read_build_options(args.build_options)
    print(
        render_release_notes(
            metadata,
            args.package_version,
            args.repository,
            build_options,
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
