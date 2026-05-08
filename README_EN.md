# r8125-driver-packages

[中文](README.md)

Automated packaging for the Realtek `r8125` 2.5G Ethernet driver.

This is a standalone packaging project, not a fork of a DKMS package repository. It discovers mirrored Realtek source archives, injects build options maintained by this repository, and publishes distribution packages through GitHub Actions.

The first supported output is a Debian/Proxmox VE DKMS source package named `r8125-dkms`. Future package backends can add OpenWrt `ipk`/`apk`, RPM, Arch, or other distribution formats without changing the upstream source discovery flow.

## What This Builds

The Debian/PVE artifact is a DKMS source package:

```text
r8125-dkms_<driver-version>-<pkgrel>_all.deb
```

It does not contain a prebuilt kernel module. When installed on Debian or Proxmox VE, DKMS builds `r8125.ko` against the kernel headers available on the target system.

## Source Mirrors

The workflow discovers the newest Realtek source archive from mirrored release assets. If multiple mirrors provide the same driver version, the current source order is used as the tie-breaker:

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

## Local Build

On a Debian or Ubuntu build host:

```sh
python3 scripts/discover-source.py --include-prereleases --pretty > build-source.json
python3 scripts/fetch-source.py --metadata build-source.json --pretty > source-metadata.json
VERSION="$(python3 -c 'import json; print(json.load(open("source-metadata.json"))["driver_version"])')"
SOURCE="$(python3 -c 'import json; print(json.load(open("source-metadata.json"))["source_path"])')"
scripts/build-deb.sh --source "$SOURCE" --version "$VERSION" --pkgrel 1
scripts/smoke-test-deb.sh "dist/r8125-dkms_${VERSION}-1_all.deb" "$VERSION"
```

## GitHub Releases

`release-deb.yml` can run on a schedule or manually. It publishes:

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

## First Publication

Create a new GitHub repository named `r8125-driver-packages` and push this project as a normal repository, not as a fork. After the first push, run the `Release Debian package` workflow manually from GitHub Actions:

```text
pkgrel: 1
include_prereleases: true
force: false
```

`Test Debian package` runs automatically after each push. `Release Debian package` also runs every Monday at 03:27 UTC and skips publishing when the target release already exists.

## Install On Proxmox VE Or Debian

Install DKMS and matching kernel headers first.

Proxmox VE:

```sh
sudo apt update
sudo apt install dkms proxmox-default-headers
```

Debian:

```sh
sudo apt update
sudo apt install dkms linux-headers-amd64
```

Then install the published `.deb`:

```sh
sudo apt install ./r8125-dkms_<version>_all.deb
```

Check DKMS status:

```sh
dkms status -m r8125
```
