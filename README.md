# r8125-driver-packages

[English](README_EN.md)

Realtek `r8125` 2.5G 以太网驱动的自动化打包项目。

这是一个独立的打包项目，不是任何 DKMS 包仓库的 fork。项目会从可信镜像获取 Realtek 驱动源码，注入本仓库维护的构建参数，并发布面向不同发行版的软件包。

当前首个支持的产物是 Debian/Proxmox VE 可用的 DKMS 源码包，包名保持为 `r8125-dkms`。后续可以在同一源码发现流程上继续扩展 OpenWrt `ipk`/`apk`、RPM、Arch 等包格式。

## 构建产物

Debian/PVE 产物是 DKMS 源码包：

```text
r8125-dkms_<driver-version>-<pkgrel>_all.deb
```

它不包含预编译内核模块。安装到 Debian 或 Proxmox VE 后，DKMS 会使用目标系统上的内核头文件编译 `r8125.ko`。

## 源码来源

项目从镜像 release assets 中获取 Realtek 源码归档。如果多个镜像提供相同驱动版本，则按当前源顺序作为优先级：

1. `openwrt/rtl8125`
2. `devome/r8125-dkms`

Realtek 官方下载站可能要求验证码，因此不作为无人值守 CI 的主源码来源。

源码选择、归因和可追溯性说明见 [UPSTREAM.md](UPSTREAM.md)。

## DKMS 构建参数

包内的 `dkms.conf` 会注入以下上游 Makefile 参数：

```text
CONFIG_ASPM=n
ENABLE_EEE=n
ENABLE_MULTIPLE_TX_QUEUE=y
ENABLE_PTP_SUPPORT=y
ENABLE_RSS_SUPPORT=y
```

其中面向性能和延迟的核心参数是关闭 ASPM、关闭 EEE、启用多 TX 队列和启用 RSS。PTP 作为硬件时间戳功能保留启用。

## 发布文件

每个 Release 包含：

```text
r8125-<driver-version>.tar.*
r8125-dkms_<driver-version>-<pkgrel>_all.deb
SHA256SUMS
provenance.json
release-notes.md
```

Release tag 与 Debian 包版本保持接近：

```text
v<driver-version>-<pkgrel>
```

示例：

```text
v9.017.01-1
```

## 在 Proxmox VE 或 Debian 上安装

先安装 DKMS 和当前内核对应的 headers。

Proxmox VE：

```sh
sudo apt update
sudo apt install dkms proxmox-default-headers
```

Debian：

```sh
sudo apt update
sudo apt install dkms linux-headers-amd64
```

然后安装本项目发布的 `.deb`：

```sh
sudo apt install ./r8125-dkms_<version>_all.deb
```

检查 DKMS 状态：

```sh
dkms status -m r8125
```

## 本地构建

需要自行构建时，可在 Debian 或 Ubuntu 构建主机上运行：

```sh
python3 scripts/discover-source.py --include-prereleases --pretty > build-source.json
python3 scripts/fetch-source.py --metadata build-source.json --pretty > source-metadata.json
VERSION="$(python3 -c 'import json; print(json.load(open("source-metadata.json"))["driver_version"])')"
SOURCE="$(python3 -c 'import json; print(json.load(open("source-metadata.json"))["source_path"])')"
scripts/build-deb.sh --source "$SOURCE" --version "$VERSION" --pkgrel 1
scripts/smoke-test-deb.sh "dist/r8125-dkms_${VERSION}-1_all.deb" "$VERSION"
```
