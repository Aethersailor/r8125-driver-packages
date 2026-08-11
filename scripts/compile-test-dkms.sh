#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "Usage: scripts/compile-test-dkms.sh <deb> <driver-version> [minimum-kernel-count]" >&2
    exit 2
fi

DEB_PATH="$1"
DRIVER_VERSION="$2"
MINIMUM_KERNEL_COUNT="${3:-1}"

if [[ "$EUID" -ne 0 ]]; then
    echo "compile-test-dkms.sh must run as root inside an ephemeral CI runner" >&2
    exit 1
fi
if [[ ! -f "$DEB_PATH" ]]; then
    echo "Debian package not found: $DEB_PATH" >&2
    exit 1
fi
if [[ ! "$DRIVER_VERSION" =~ ^[0-9][0-9.]*$ ]]; then
    echo "Invalid driver version: $DRIVER_VERSION" >&2
    exit 2
fi
if [[ ! "$MINIMUM_KERNEL_COUNT" =~ ^[1-9][0-9]*$ ]]; then
    echo "Invalid minimum kernel count: $MINIMUM_KERNEL_COUNT" >&2
    exit 2
fi

for command in dkms dpkg-deb find; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Required command not found: $command" >&2
        exit 1
    fi
done

WORK_DIR="$(mktemp -d)"
SOURCE_TREE="/usr/src/r8125-$DRIVER_VERSION"
DKMS_ADDED="false"

cleanup() {
    if [[ "$DKMS_ADDED" == "true" ]]; then
        dkms remove -m r8125 -v "$DRIVER_VERSION" --all >/dev/null 2>&1 || true
    fi
    rm -rf "$WORK_DIR"
    if [[ -d "$SOURCE_TREE" ]]; then
        rm -rf "$SOURCE_TREE"
    fi
}
trap cleanup EXIT

if [[ -e "$SOURCE_TREE" ]]; then
    echo "Refusing to replace an existing DKMS source tree: $SOURCE_TREE" >&2
    exit 1
fi

dpkg-deb -x "$DEB_PATH" "$WORK_DIR/package"
PACKAGE_SOURCE="$WORK_DIR/package/usr/src/r8125-$DRIVER_VERSION"
if [[ ! -f "$PACKAGE_SOURCE/dkms.conf" ]]; then
    echo "Package does not contain the expected DKMS source tree" >&2
    exit 1
fi

install -d -m 0755 "$SOURCE_TREE"
cp -a "$PACKAGE_SOURCE/." "$SOURCE_TREE/"
dkms add -m r8125 -v "$DRIVER_VERSION"
DKMS_ADDED="true"

mapfile -t KERNEL_VERSIONS < <(
    find /usr/src -path '/usr/src/linux-headers-*/include/config/kernel.release' -type f -print \
        | while IFS= read -r release_file; do
            cat "$release_file"
        done \
        | sort -uV
)

if (( ${#KERNEL_VERSIONS[@]} < MINIMUM_KERNEL_COUNT )); then
    echo "Found ${#KERNEL_VERSIONS[@]} configured kernel header sets; expected at least $MINIMUM_KERNEL_COUNT" >&2
    exit 1
fi

for kernel_version in "${KERNEL_VERSIONS[@]}"; do
    header_dir="/lib/modules/$kernel_version/build"
    if [[ ! -d "$header_dir" ]]; then
        echo "Kernel build directory not found: $header_dir" >&2
        exit 1
    fi
    echo "Compiling r8125 $DRIVER_VERSION for Linux $kernel_version"
    dkms build -m r8125 -v "$DRIVER_VERSION" -k "$kernel_version" \
        --kernelsourcedir "$header_dir"
    module_path="$(find "/var/lib/dkms/r8125/$DRIVER_VERSION/$kernel_version" -type f -name 'r8125.ko*' -size +0c -print -quit)"
    if [[ -z "$module_path" ]]; then
        echo "DKMS did not produce r8125.ko for Linux $kernel_version" >&2
        exit 1
    fi
    echo "Compiled module: $module_path"
done

echo "DKMS compile test passed for ${#KERNEL_VERSIONS[@]} kernel header set(s)"
