# r8125-driver-packages

[English](README_EN.md)

Realtek `r8125` 2.5G 以太网驱动的自动化打包项目。

项目会从可信镜像获取 Realtek 驱动源码，注入本仓库维护的构建参数，并发布面向不同发行版的软件包。

当前支持 Debian/Proxmox VE 可用的 DKMS 源码包，包名保持为 `r8125-dkms`。后续可以在同一源码发现流程上继续扩展 OpenWrt `ipk`/`apk`、RPM、Arch 等包格式。

## 构建产物

Debian/PVE 产物是 DKMS 源码包：

```text
r8125-dkms_<driver-version>-<pkgrel>_all.deb
```

它不包含预编译内核模块。安装到 Debian 或 Proxmox VE 后，DKMS 会使用目标系统上的内核头文件编译 `r8125.ko`。

## 源码来源

项目从 `openwrt/rtl8125` 的 release assets 中获取 Realtek 源码归档。

Realtek 官方下载站可能要求验证码，因此不作为无人值守构建的主源码来源。

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

## 安装

安装前请先下载 Release 中的 `r8125-dkms_<version>_all.deb`。本包是 DKMS 源码包，安装时会在目标系统上为当前内核编译驱动模块。

<details>
<summary>Proxmox VE</summary>

以下流程参考了 [Evine 的 PVE RTL8125 驱动安装教程](https://evine.win/p/pve-install-realtek-8125-driver/)，并针对本项目发布的包名整理。

更新系统并安装 DKMS 与内核 headers：

```sh
sudo apt update
sudo apt upgrade
sudo apt install dkms proxmox-default-headers
```

如果使用较旧的 PVE 版本，`proxmox-default-headers` 不可用时可改用 `pve-headers`。

如需为当前系统中已安装的多个 PVE 内核准备 headers，可执行：

```sh
headers=$(dpkg -l | awk '/^ii.+kernel-[0-9]+\.[0-9]+\.[0-9]/{gsub(/-signed/, ""); gsub(/kernel/, "headers"); print $2}' | tr "\n" " ")
sudo apt install -y $headers
```

安装下载好的 DKMS 包：

```sh
sudo dpkg -i r8125-dkms_*.deb
```

如果需要为旧内核补装模块，先查看 DKMS 状态和已安装内核版本：

```sh
dkms status
dpkg -l | awk '/^ii.+kernel-[0-9]+\.[0-9]+\.[0-9]/{gsub(/proxmox-kernel-|pve-kernel-|-signed/, ""); print $2}'
```

然后按需指定驱动版本和内核版本：

```sh
sudo dkms install r8125/<driver_version> -k <kernel_version>
```

禁用内核自带的 `r8169` 驱动，避免重启后继续加载旧驱动：

```sh
echo "blacklist r8169" | sudo tee -a /etc/modprobe.d/r8125-dkms.conf
sudo update-grub
sudo update-initramfs -u -k all
sudo reboot
```

重启后确认网卡已加载 `r8125`：

```sh
lspci | grep RTL8125
lspci -s <pci-id> -k
```

</details>

<details>
<summary>Debian</summary>

更新系统并安装 DKMS 与当前内核 headers：

```sh
sudo apt update
sudo apt install dkms linux-headers-$(uname -r)
```

如果使用 Debian 通用内核元包，也可以安装：

```sh
sudo apt install dkms linux-headers-amd64
```

安装下载好的 DKMS 包：

```sh
sudo dpkg -i r8125-dkms_*.deb
```

如需切换掉内核自带的 `r8169` 驱动，可禁用它并重建 initramfs：

```sh
echo "blacklist r8169" | sudo tee -a /etc/modprobe.d/r8125-dkms.conf
sudo update-initramfs -u -k all
sudo reboot
```

检查 DKMS 状态：

```sh
dkms status -m r8125
```

确认网卡已加载 `r8125`：

```sh
lspci | grep RTL8125
lspci -s <pci-id> -k
```

</details>

## 本地构建

需要自行构建时，可在 Debian 或 Ubuntu 构建主机上运行：

```sh
python3 scripts/discover-source.py --pretty > build-source.json
python3 scripts/fetch-source.py --metadata build-source.json --pretty > source-metadata.json
VERSION="$(python3 -c 'import json; print(json.load(open("source-metadata.json"))["driver_version"])')"
SOURCE="$(python3 -c 'import json; print(json.load(open("source-metadata.json"))["source_path"])')"
scripts/build-deb.sh --source "$SOURCE" --version "$VERSION" --pkgrel 1
scripts/smoke-test-deb.sh "dist/r8125-dkms_${VERSION}-1_all.deb" "$VERSION"
```
