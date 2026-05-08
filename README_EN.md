# r8125-driver-packages

[中文](README.md)

Automated packaging for the Realtek `r8125` 2.5G Ethernet driver.

This is a standalone packaging project, not a fork of a DKMS package repository. It obtains Realtek source archives from trusted mirrors, injects build options maintained by this repository, and publishes distribution packages for supported systems.

The first supported output is a Debian/Proxmox VE DKMS source package named `r8125-dkms`. Future package backends can add OpenWrt `ipk`/`apk`, RPM, Arch, or other distribution formats without changing the upstream source discovery flow.

## What This Builds

The Debian/PVE artifact is a DKMS source package:

```text
r8125-dkms_<driver-version>-<pkgrel>_all.deb
```

It does not contain a prebuilt kernel module. When installed on Debian or Proxmox VE, DKMS builds `r8125.ko` against the kernel headers available on the target system.

## Source Mirrors

The project obtains Realtek source archives from mirrored release assets. If multiple mirrors provide the same driver version, the current source order is used as the tie-breaker:

1. `openwrt/rtl8125`
2. `devome/r8125-dkms`

Realtek's official download site can require CAPTCHA, so it is not used as the primary unattended CI source.

See [UPSTREAM.md](UPSTREAM.md) for source attribution and provenance details.

## DKMS Build Options

The package injects these upstream Makefile options through `dkms.conf`:

```text
CONFIG_ASPM=n
ENABLE_EEE=n
ENABLE_MULTIPLE_TX_QUEUE=y
ENABLE_PTP_SUPPORT=y
ENABLE_RSS_SUPPORT=y
```

The performance and latency oriented options are ASPM off, EEE off, multiple TX queues, and RSS. PTP is kept enabled as a hardware timestamping feature.

## Release Assets

Each release publishes:

```text
r8125-<driver-version>.tar.*
r8125-dkms_<driver-version>-<pkgrel>_all.deb
SHA256SUMS
provenance.json
release-notes.md
```

Release tags stay close to the Debian package version:

```text
v<driver-version>-<pkgrel>
```

Example:

```text
v9.017.01-1
```

## Installation

Download `r8125-dkms_<version>_all.deb` from Releases before installing. This is a DKMS source package, so the driver module is built on the target system during package installation.

<details>
<summary>Proxmox VE</summary>

The flow below follows [Evine's PVE RTL8125 driver installation guide](https://evine.win/p/pve-install-realtek-8125-driver/) and adapts it to this project's package name.

Update the system and install DKMS with matching kernel headers:

```sh
sudo apt update
sudo apt upgrade
sudo apt install dkms proxmox-default-headers
```

For older PVE releases where `proxmox-default-headers` is unavailable, use `pve-headers` instead.

To install headers for all currently installed PVE kernels:

```sh
headers=$(dpkg -l | awk '/^ii.+kernel-[0-9]+\.[0-9]+\.[0-9]/{gsub(/-signed/, ""); gsub(/kernel/, "headers"); print $2}' | tr "\n" " ")
sudo apt install -y $headers
```

Install the downloaded DKMS package:

```sh
sudo dpkg -i r8125-dkms_*.deb
```

If older kernels also need the module, inspect DKMS status and installed kernel versions first:

```sh
dkms status
dpkg -l | awk '/^ii.+kernel-[0-9]+\.[0-9]+\.[0-9]/{gsub(/proxmox-kernel-|pve-kernel-|-signed/, ""); print $2}'
```

Then install the module for the required kernel explicitly:

```sh
sudo dkms install r8125/<driver_version> -k <kernel_version>
```

Blacklist the in-kernel `r8169` driver so the system loads `r8125` after reboot:

```sh
echo "blacklist r8169" | sudo tee -a /etc/modprobe.d/r8125-dkms.conf
sudo update-grub
sudo update-initramfs -u -k all
sudo reboot
```

After reboot, verify that the NIC is using `r8125`:

```sh
lspci | grep RTL8125
lspci -s <pci-id> -k
```

</details>

<details>
<summary>Debian</summary>

Update the system and install DKMS with headers for the running kernel:

```sh
sudo apt update
sudo apt install dkms linux-headers-$(uname -r)
```

If you use Debian's generic kernel metapackage, this is also appropriate:

```sh
sudo apt install dkms linux-headers-amd64
```

Install the downloaded DKMS package:

```sh
sudo dpkg -i r8125-dkms_*.deb
```

If you need to replace the in-kernel `r8169` driver, blacklist it and rebuild initramfs:

```sh
echo "blacklist r8169" | sudo tee -a /etc/modprobe.d/r8125-dkms.conf
sudo update-initramfs -u -k all
sudo reboot
```

Check DKMS status:

```sh
dkms status -m r8125
```

Verify that the NIC is using `r8125`:

```sh
lspci | grep RTL8125
lspci -s <pci-id> -k
```

</details>

## Local Build

If you need to build the package yourself, run the following on a Debian or Ubuntu build host:

```sh
python3 scripts/discover-source.py --include-prereleases --pretty > build-source.json
python3 scripts/fetch-source.py --metadata build-source.json --pretty > source-metadata.json
VERSION="$(python3 -c 'import json; print(json.load(open("source-metadata.json"))["driver_version"])')"
SOURCE="$(python3 -c 'import json; print(json.load(open("source-metadata.json"))["source_path"])')"
scripts/build-deb.sh --source "$SOURCE" --version "$VERSION" --pkgrel 1
scripts/smoke-test-deb.sh "dist/r8125-dkms_${VERSION}-1_all.deb" "$VERSION"
```
