#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_ARCHIVE=""
DRIVER_VERSION=""
PKGREL="${PKGREL:-1}"
BUILD_OPTIONS_FILE="$ROOT_DIR/config/build-options.env"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build/deb"

usage() {
    cat <<'EOF'
Usage: scripts/build-deb.sh --source <archive> --version <driver-version> [--pkgrel <revision>] [--build-options <file>]
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source)
            SOURCE_ARCHIVE="$2"
            shift 2
            ;;
        --version)
            DRIVER_VERSION="$2"
            shift 2
            ;;
        --pkgrel)
            PKGREL="$2"
            shift 2
            ;;
        --build-options)
            BUILD_OPTIONS_FILE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -z "$SOURCE_ARCHIVE" || -z "$DRIVER_VERSION" ]]; then
    usage >&2
    exit 2
fi

if [[ ! -f "$BUILD_OPTIONS_FILE" ]]; then
    echo "Build options file not found: $BUILD_OPTIONS_FILE" >&2
    exit 1
fi

PACKAGE_VERSION="${DRIVER_VERSION}-${PKGREL}"
PACKAGE_ROOT="$BUILD_DIR/package"
EXTRACT_DIR="$BUILD_DIR/source"
SRC_DIR="$PACKAGE_ROOT/usr/src/r8125-$DRIVER_VERSION"
DOC_DIR="$PACKAGE_ROOT/usr/share/doc/r8125-dkms"

rm -rf "$BUILD_DIR"
mkdir -p "$EXTRACT_DIR" "$SRC_DIR" "$DOC_DIR" "$PACKAGE_ROOT/DEBIAN" "$DIST_DIR"

tar -xf "$SOURCE_ARCHIVE" -C "$EXTRACT_DIR"
mapfile -t UPSTREAM_ROOTS < <(find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 -type d)
if [[ "${#UPSTREAM_ROOTS[@]}" -ne 1 || ! -d "${UPSTREAM_ROOTS[0]}/src" ]]; then
    echo "Unable to locate upstream src directory in $SOURCE_ARCHIVE" >&2
    exit 1
fi
UPSTREAM_ROOT="${UPSTREAM_ROOTS[0]}"

find "$UPSTREAM_ROOT/src" -mindepth 1 -maxdepth 1 ! -name 'Makefile_linux24x' -exec cp -a {} "$SRC_DIR/" \;

PATCH_DIR="$ROOT_DIR/patches/$DRIVER_VERSION"
if [[ -d "$PATCH_DIR" ]]; then
    echo "Applying patches for r8125 $DRIVER_VERSION"
    for patch_file in "$PATCH_DIR"/*.patch; do
        [[ -e "$patch_file" ]] || continue
        echo "Applying patch: $(basename "$patch_file")"
        patch -d "$SRC_DIR" -p1 < "$patch_file"
    done
fi

if [[ -f "$UPSTREAM_ROOT/README" ]]; then
    install -m 0644 "$UPSTREAM_ROOT/README" "$DOC_DIR/README"
fi
install -m 0644 "$ROOT_DIR/LICENSE" "$DOC_DIR/LICENSE.r8125-driver-packages"
install -m 0644 "$ROOT_DIR/packaging/debian/copyright" "$DOC_DIR/copyright"

awk -v version="$DRIVER_VERSION" -v build_options_file="$BUILD_OPTIONS_FILE" '
    function emit_build_options() {
        while ((getline option < build_options_file) > 0) {
            if (option ~ /^[[:space:]]*($|#)/) {
                continue
            }
            if (option !~ /^[A-Za-z_][A-Za-z0-9_]*=[A-Za-z0-9_.-]+$/) {
                printf "Invalid build option: %s\n", option > "/dev/stderr"
                exit 1
            }
            print "    " option " \\"
        }
        close(build_options_file)
    }
    {
        gsub("@PKGVER@", version)
    }
    /@BUILD_OPTIONS@/ {
        emit_build_options()
        next
    }
    { print }
' "$ROOT_DIR/packaging/debian/dkms.conf.in" > "$SRC_DIR/dkms.conf"
sed "s/@PACKAGE_VERSION@/$PACKAGE_VERSION/g" "$ROOT_DIR/packaging/debian/control.in" > "$PACKAGE_ROOT/DEBIAN/control"
install -m 0755 "$ROOT_DIR/packaging/debian/postinst" "$PACKAGE_ROOT/DEBIAN/postinst"
install -m 0755 "$ROOT_DIR/packaging/debian/prerm" "$PACKAGE_ROOT/DEBIAN/prerm"

find "$PACKAGE_ROOT" -type d -exec chmod 0755 {} \;
find "$PACKAGE_ROOT" -type f -not -path '*/DEBIAN/postinst' -not -path '*/DEBIAN/prerm' -exec chmod 0644 {} \;

DEB_PATH="$DIST_DIR/r8125-dkms_${PACKAGE_VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$PACKAGE_ROOT" "$DEB_PATH"
echo "$DEB_PATH"
