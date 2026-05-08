# Upstream Source Policy

This repository does not vendor the Realtek `r8125` driver source in Git.

Package builds use mirrored Realtek source archives from:

1. `openwrt/rtl8125`

The downloaded source archive is republished as a release asset together with
the generated Debian package, `SHA256SUMS`, and `provenance.json`.

`provenance.json` records:

- selected mirror
- source repository
- source release URL
- source asset URL
- source SHA256
- driver version
- package version
- DKMS build options
- build run id

The Realtek driver source keeps its upstream license. Files in this packaging
repository are licensed under the MIT license unless stated otherwise.
