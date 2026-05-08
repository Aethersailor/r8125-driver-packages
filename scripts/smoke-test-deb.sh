#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "Usage: scripts/smoke-test-deb.sh <deb> <driver-version> [build-options-file]" >&2
    exit 2
fi

DEB_PATH="$1"
DRIVER_VERSION="$2"
BUILD_OPTIONS_FILE="${3:-config/build-options.env}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

dpkg-deb -I "$DEB_PATH" > "$TMP_DIR/control.txt"
dpkg-deb -c "$DEB_PATH" > "$TMP_DIR/files.txt"
dpkg-deb -x "$DEB_PATH" "$TMP_DIR/root"

grep -q '^ Package: r8125-dkms$' "$TMP_DIR/control.txt"
grep -q "./usr/src/r8125-$DRIVER_VERSION/dkms.conf" "$TMP_DIR/files.txt"
while IFS= read -r option; do
    case "$option" in
        ""|\#*) continue ;;
    esac
    grep -Fq "$option" "$TMP_DIR/root/usr/src/r8125-$DRIVER_VERSION/dkms.conf"
done < "$BUILD_OPTIONS_FILE"

echo "smoke test passed: $DEB_PATH"
