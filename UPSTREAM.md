# Upstream Source Policy

This repository does not vendor the Realtek `r8125` driver source in Git.

Realtek's official download list is the version authority:

- https://www.realtek.com/Download/List?cate_id=584

Package builds use mirrored Realtek source archives from these repositories,
in priority order:

1. `openwrt/rtl8125`
2. `danixland/r8125`

The discovery process applies these rules:

- query Realtek before selecting a mirror
- reject mirror versions newer than Realtek's latest published version
- require a GitHub-recorded SHA256 digest for every candidate asset
- select the highest eligible version
- prefer the first configured mirror when versions are equal
- recompute and verify SHA256 after download

The Realtek download flow can require confirmation or CAPTCHA, so it is not
used for unattended source downloads. A GitHub asset digest verifies the bytes
against the selected mirror; it is not a Realtek signature.

The downloaded source archive is republished as a release asset together with
the generated Debian package, `SHA256SUMS`, and `provenance.json`.

`provenance.json` records:

- selected mirror
- source repository
- source release URL
- source asset URL
- source SHA256
- Realtek-confirmed driver version
- Realtek download item id and update time
- driver version
- package version
- DKMS build options
- build run id

The Realtek driver source keeps its upstream license. Files in this packaging
repository are licensed under the MIT license unless stated otherwise.
