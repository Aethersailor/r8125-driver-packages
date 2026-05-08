# r8125-driver-packages

Automated packaging for the Realtek `r8125` 2.5G Ethernet driver.

This is a standalone packaging project, not a fork of a DKMS package
repository. It discovers mirrored Realtek source archives, injects local build
options, and publishes distribution packages from this repository's workflows.

The first supported output is a Debian/Proxmox VE DKMS source package named
`r8125-dkms`. Future package backends can add OpenWrt `ipk`/`apk`, RPM, Arch,
or other distribution formats without changing the upstream source discovery
flow.

## What This Builds

The Debian package is a DKMS source package:

```text
r8125-dkms_<driver-version>-<pkgrel>_all.deb
```

It does not contain a prebuilt kernel module. When installed on Debian or
Proxmox VE, DKMS builds `r8125.ko` against the local kernel headers.

## Source Mirrors

The workflow discovers the newest Realtek source archive from mirrored release
assets. If two mirrors provide the same driver version, the current source
order is used as the tie-breaker:

1. `openwrt/rtl8125`
2. `devome/r8125-dkms`

Realtek's official download site can require CAPTCHA, so it is not used as the
primary unattended CI source.

See [UPSTREAM.md](UPSTREAM.md) for source and attribution details.

## DKMS Build Options

The package injects these upstream Makefile options through `dkms.conf`:

```text
CONFIG_ASPM=n
ENABLE_EEE=n
ENABLE_MULTIPLE_TX_QUEUE=y
ENABLE_PTP_SUPPORT=y
ENABLE_RSS_SUPPORT=y
```

The performance and latency oriented options are ASPM off, EEE off, multiple TX
queues, and RSS. PTP is enabled as an additional hardware timestamping feature.

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

Release tags follow the Debian package version:

```text
v<driver-version>-<pkgrel>
```

Example:

```text
v9.017.01-1
```

## First Publication

Create a new GitHub repository named `r8125-driver-packages` and push this
project as a normal repository, not as a fork. After the first push, run the
`Release Debian package` workflow manually from GitHub Actions:

```text
pkgrel: 1
include_prereleases: true
force: false
```

The first test workflow runs automatically on push. The release workflow also
runs every Monday at 03:27 UTC and skips publishing when the target release
already exists.

## Install On Proxmox VE Or Debian

Install DKMS and matching kernel headers first:

```sh
sudo apt update
sudo apt install dkms proxmox-default-headers
```

For Debian instead of Proxmox VE, install the appropriate `linux-headers-*`
package, for example:

```sh
sudo apt install dkms linux-headers-amd64
```

Then install the package:

```sh
sudo apt install ./r8125-dkms_<version>_all.deb
```

Check DKMS status:

```sh
dkms status -m r8125
```
