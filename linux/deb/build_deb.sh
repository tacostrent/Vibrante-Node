#!/usr/bin/env bash
# build_deb.sh — Build a Vibrante-Node .deb package for Ubuntu/Debian
#
# Usage:
#   bash build_deb.sh [OPTIONS]
#
# Options:
#   --wheel PATH     Path to the vibrante-node .whl to install.
#                    Default: auto-detected from ../../dist/
#   --version VER    Package version (default: read from wheel filename).
#   --python CMD     Python 3.10+ interpreter to use (default: python3).
#   --help           Show this help.
#
# Requirements:
#   dpkg-deb, python3 (>= 3.10), pip3
#
# The package is installed to /opt/vibrante-node/ with a launcher symlink at
# /usr/bin/vibrante-node.  System PyQt5 (python3-pyqt5) is used as a
# dependency rather than bundling Qt — this keeps the .deb small and lets it
# share system libraries with other Qt apps.
#
# Output:
#   linux/build/vibrante-node_<version>_amd64.deb

set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log()  { echo "[deb] $*"; }
err()  { echo "[deb] ERROR: $*" >&2; exit 1; }
need() { command -v "$1" &>/dev/null || err "Required tool not found: $1"; }

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD_DIR="${REPO_ROOT}/linux/build"
DEB_SRC="${SCRIPT_DIR}"

PYTHON_CMD="python3"
WHEEL_PATH=""
VERSION=""

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)
            sed -n '2,/^# Requirements/{ /^#/{ s/^# \{0,1\}//; p }; /^[^#]/q }' "$0"
            exit 0
            ;;
        --wheel)   WHEEL_PATH="$2"; shift 2 ;;
        --version) VERSION="$2";    shift 2 ;;
        --python)  PYTHON_CMD="$2"; shift 2 ;;
        *) err "Unknown option: $1  (use --help for usage)" ;;
    esac
done

# ---------------------------------------------------------------------------
# Platform check
# ---------------------------------------------------------------------------

if [[ "$(uname -s)" != "Linux" ]]; then
    err ".deb builds require Linux.  Current OS: $(uname -s)"
fi

# ---------------------------------------------------------------------------
# Required tools
# ---------------------------------------------------------------------------

need dpkg-deb
need "${PYTHON_CMD}"
need pip3

# ---------------------------------------------------------------------------
# Resolve wheel
# ---------------------------------------------------------------------------

if [[ -z "${WHEEL_PATH}" ]]; then
    WHEEL_PATH="$(ls -t "${REPO_ROOT}/dist"/vibrante_node-*.whl 2>/dev/null | head -1 || true)"
    [[ -n "${WHEEL_PATH}" ]] || err "No vibrante-node wheel found in dist/.  Run:  python -m build --wheel"
fi
[[ -f "${WHEEL_PATH}" ]] || err "Wheel not found: ${WHEEL_PATH}"

if [[ -z "${VERSION}" ]]; then
    VERSION="$(basename "${WHEEL_PATH}" | sed 's/vibrante_node-\([^-]*\)-.*/\1/')"
fi

log "Wheel:   ${WHEEL_PATH}"
log "Version: ${VERSION}"

# ---------------------------------------------------------------------------
# Prepare staging area
# ---------------------------------------------------------------------------

STAGING="${BUILD_DIR}/deb-staging/vibrante-node_${VERSION}_amd64"
OPT_DIR="${STAGING}/opt/vibrante-node"
BIN_DIR="${STAGING}/usr/bin"
SHARE_DIR="${STAGING}/usr/share"
DEBIAN_DIR="${STAGING}/DEBIAN"

log "Staging in ${STAGING} ..."
rm -rf "${STAGING}"
mkdir -p "${OPT_DIR}" "${BIN_DIR}" \
         "${SHARE_DIR}/applications" \
         "${SHARE_DIR}/icons/hicolor/256x256/apps" \
         "${DEBIAN_DIR}"

# ---------------------------------------------------------------------------
# Install the wheel into /opt/vibrante-node/
# ---------------------------------------------------------------------------

log "Installing vibrante-node wheel into ${OPT_DIR} ..."
pip3 install \
    --quiet \
    --target "${OPT_DIR}/lib" \
    --no-deps \
    "${WHEEL_PATH}"

# Verify installation
[[ -f "${OPT_DIR}/lib/vibrante_node/__init__.py" ]] || \
    err "Wheel install failed — vibrante_node package not found in ${OPT_DIR}/lib/"

# ---------------------------------------------------------------------------
# Create the launcher script at /usr/bin/vibrante-node
# ---------------------------------------------------------------------------

log "Creating launcher at /usr/bin/vibrante-node ..."
cat > "${BIN_DIR}/vibrante-node" <<'LAUNCHER'
#!/bin/bash
# Launcher for Vibrante-Node (.deb install)
#
# The app is installed under /opt/vibrante-node/lib/ as a pip target dir
# (no --user, no virtualenv).  We add it to PYTHONPATH before launching
# so Python can find vibrante_node and src packages.
#
# Qt platform: defaults to xcb (X11) to avoid fragile PyQt5 Wayland support.
# Override by setting QT_QPA_PLATFORM before calling this script.

set -e

OPT_LIB="/opt/vibrante-node/lib"

if [ -z "${QT_QPA_PLATFORM:-}" ]; then
    export QT_QPA_PLATFORM=xcb
fi

export PYTHONPATH="${OPT_LIB}${PYTHONPATH:+:${PYTHONPATH}}"
exec python3 -c "from vibrante_node.app import main; main()" "$@"
LAUNCHER
chmod +x "${BIN_DIR}/vibrante-node"

# ---------------------------------------------------------------------------
# Desktop entry and icon
# ---------------------------------------------------------------------------

log "Installing desktop entry and icon ..."

cp "${DEB_SRC}/vibrante-node.desktop" \
   "${SHARE_DIR}/applications/vibrante-node.desktop"

ICON_SRC="${REPO_ROOT}/icons/vibrante-node-resize_main_logo.png"
if [[ -f "${ICON_SRC}" ]]; then
    cp "${ICON_SRC}" \
       "${SHARE_DIR}/icons/hicolor/256x256/apps/vibrante-node.png"
else
    log "WARNING: icon not found at ${ICON_SRC}"
fi

# ---------------------------------------------------------------------------
# DEBIAN/ control files
# ---------------------------------------------------------------------------

log "Writing DEBIAN/ control files ..."

# Calculate installed size (in KB, as dpkg expects)
INSTALLED_SIZE_KB="$(du -sk "${OPT_DIR}" | cut -f1)"

sed \
    -e "s/__VERSION__/${VERSION}/" \
    -e "s/__INSTALLED_SIZE__/${INSTALLED_SIZE_KB}/" \
    "${DEB_SRC}/control" > "${DEBIAN_DIR}/control"

# postinst — refresh desktop caches
cp "${DEB_SRC}/postinst" "${DEBIAN_DIR}/postinst"
chmod 0755 "${DEBIAN_DIR}/postinst"

# ---------------------------------------------------------------------------
# Build the .deb
# ---------------------------------------------------------------------------

OUTPUT_DEB="${BUILD_DIR}/vibrante-node_${VERSION}_amd64.deb"
rm -f "${OUTPUT_DEB}"

log "Building .deb ..."
dpkg-deb --build --root-owner-group "${STAGING}" "${OUTPUT_DEB}"

# ---------------------------------------------------------------------------
# Verify and report
# ---------------------------------------------------------------------------

[[ -f "${OUTPUT_DEB}" ]] || err "dpkg-deb ran but output not found: ${OUTPUT_DEB}"

SIZE_MB="$(du -m "${OUTPUT_DEB}" | cut -f1)"
log ""
log "================================================================"
log "  .deb package built successfully!"
log "  Output : ${OUTPUT_DEB}"
log "  Size   : ${SIZE_MB} MB"
log "================================================================"
log ""
log "Install with:"
log "  sudo dpkg -i ${OUTPUT_DEB}"
log "  sudo apt-get install -f   # fix any missing deps"
log ""
log "Verify:"
log "  dpkg -l vibrante-node"
log "  QT_QPA_PLATFORM=offscreen vibrante-node --help"
