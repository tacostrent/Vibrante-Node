#!/usr/bin/env bash
# build_appimage.sh — Build a Vibrante-Node AppImage for Linux x86_64
#
# Usage:
#   bash build_appimage.sh [OPTIONS]
#
# Options:
#   --wheel PATH     Path to the vibrante-node .whl file to bundle.
#                    Default: auto-detected from ../../dist/
#   --version VER    App version string (default: read from wheel filename).
#   --python VER     Python version to bundle (default: 3.10.14).
#   --skip-download  Skip downloading base AppImage if already in cache.
#   --help           Show this help.
#
# Requirements (must be on PATH or in linux/build/cache/):
#   wget, chmod, file
#   appimagetool (auto-downloaded if missing)
#   Python 3.10 base AppImage (auto-downloaded if missing)
#
# Output:
#   linux/build/Vibrante-Node-<version>-x86_64.AppImage
#
# Reproducibility:
#   Set SOURCE_DATE_EPOCH before calling this script to freeze timestamps:
#     SOURCE_DATE_EPOCH=0 bash build_appimage.sh
#
# Notes:
#   - The script runs on Linux only (AppImage format is Linux-specific).
#   - PyQt5 Wayland support in 5.15 is fragile; AppRun defaults QT_QPA_PLATFORM
#     to xcb.  Users can override this in their environment.
#   - SELinux (Rocky/Alma): local TCP connections (Houdini bridge) require no
#     special policy.  If users hit SELinux denials, see linux/README.md.

set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log()  { echo "[appimage] $*"; }
err()  { echo "[appimage] ERROR: $*" >&2; exit 1; }
need() {
    command -v "$1" &>/dev/null || err "Required tool not found: $1  (install it and retry)"
}

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD_DIR="${REPO_ROOT}/linux/build"
CACHE_DIR="${BUILD_DIR}/cache"
APPIMAGE_DIR="${SCRIPT_DIR}"

PYTHON_VERSION="3.10.19"
SKIP_DOWNLOAD=0
WHEEL_PATH=""
APP_VERSION=""

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)
            sed -n '2,/^# Requirements/{ /^#/{ s/^# \{0,1\}//; p }; /^[^#]/q }' "$0"
            exit 0
            ;;
        --wheel)      WHEEL_PATH="$2";    shift 2 ;;
        --version)    APP_VERSION="$2";   shift 2 ;;
        --python)     PYTHON_VERSION="$2"; shift 2 ;;
        --skip-download) SKIP_DOWNLOAD=1; shift   ;;
        *) err "Unknown option: $1  (use --help for usage)" ;;
    esac
done

# ---------------------------------------------------------------------------
# Platform check
# ---------------------------------------------------------------------------

if [[ "$(uname -s)" != "Linux" ]]; then
    err "AppImage builds require Linux.  Current OS: $(uname -s)"
fi
if [[ "$(uname -m)" != "x86_64" ]]; then
    err "This script builds x86_64 AppImages only.  Current arch: $(uname -m)"
fi

# ---------------------------------------------------------------------------
# Required tools
# ---------------------------------------------------------------------------

need wget
need chmod
need file

# ---------------------------------------------------------------------------
# Resolve wheel
# ---------------------------------------------------------------------------

if [[ -z "${WHEEL_PATH}" ]]; then
    # Auto-detect from dist/
    WHEEL_PATH="$(ls -t "${REPO_ROOT}/dist"/vibrante_node-*.whl 2>/dev/null | head -1 || true)"
    [[ -n "${WHEEL_PATH}" ]] || err "No vibrante-node wheel found in dist/.  Run:  python -m build --wheel"
fi
[[ -f "${WHEEL_PATH}" ]] || err "Wheel not found: ${WHEEL_PATH}"

if [[ -z "${APP_VERSION}" ]]; then
    # Extract version from wheel filename  (vibrante_node-2.3.0-py3-none-any.whl)
    APP_VERSION="$(basename "${WHEEL_PATH}" | sed 's/vibrante_node-\([^-]*\)-.*/\1/')"
fi

log "Wheel:   ${WHEEL_PATH}"
log "Version: ${APP_VERSION}"
log "Python:  ${PYTHON_VERSION}"

# ---------------------------------------------------------------------------
# Prepare directories
# ---------------------------------------------------------------------------

mkdir -p "${CACHE_DIR}" "${BUILD_DIR}"

# ---------------------------------------------------------------------------
# Download appimagetool if not cached
# ---------------------------------------------------------------------------

APPIMAGETOOL="${CACHE_DIR}/appimagetool-x86_64.AppImage"

if [[ ! -f "${APPIMAGETOOL}" ]]; then
    log "Downloading appimagetool..."
    # Use a pinned release for CI reproducibility; fallback to the continuous build
    APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    wget -q --show-progress --tries=5 --timeout=60 --waitretry=15 -O "${APPIMAGETOOL}" "${APPIMAGETOOL_URL}" \
        || { log "Primary URL failed, retrying via curl..."; curl -fL --retry 5 --retry-delay 15 -o "${APPIMAGETOOL}" "${APPIMAGETOOL_URL}"; }
    chmod +x "${APPIMAGETOOL}"
    log "appimagetool downloaded to ${APPIMAGETOOL}"
else
    log "Using cached appimagetool"
fi

# ---------------------------------------------------------------------------
# Download Python 3.10 base AppImage if not cached
# ---------------------------------------------------------------------------

# Derive the minor version (e.g. 3.10 from 3.10.14)
PY_MINOR="$(echo "${PYTHON_VERSION}" | cut -d. -f1-2)"

PYTHON_APPIMAGE_NAME="python${PYTHON_VERSION}-cp${PY_MINOR//./}-cp${PY_MINOR//./}-manylinux2014_x86_64.AppImage"
PYTHON_APPIMAGE_CACHED="${CACHE_DIR}/${PYTHON_APPIMAGE_NAME}"
PYTHON_APPIMAGE_URL="https://github.com/niess/python-appimage/releases/download/python${PY_MINOR}/${PYTHON_APPIMAGE_NAME}"

if [[ ! -f "${PYTHON_APPIMAGE_CACHED}" ]] && [[ "${SKIP_DOWNLOAD}" -eq 0 ]]; then
    log "Downloading Python ${PYTHON_VERSION} base AppImage..."
    wget -q --show-progress --tries=5 --timeout=120 --waitretry=15 -O "${PYTHON_APPIMAGE_CACHED}" "${PYTHON_APPIMAGE_URL}" \
        || { log "wget failed, retrying via curl..."; curl -fL --retry 5 --retry-delay 15 -o "${PYTHON_APPIMAGE_CACHED}" "${PYTHON_APPIMAGE_URL}"; }
    chmod +x "${PYTHON_APPIMAGE_CACHED}"
    log "Cached at ${PYTHON_APPIMAGE_CACHED}"
elif [[ ! -f "${PYTHON_APPIMAGE_CACHED}" ]]; then
    err "Python base AppImage not found in cache and --skip-download was set."
else
    log "Using cached Python ${PYTHON_VERSION} AppImage"
fi

# ---------------------------------------------------------------------------
# Extract the Python base AppImage into a temporary AppDir
# ---------------------------------------------------------------------------

APPDIR="${BUILD_DIR}/Vibrante-Node-${APP_VERSION}.AppDir"

log "Extracting Python AppImage to ${APPDIR} ..."
rm -rf "${APPDIR}"
# AppImages self-extract with --appimage-extract; output goes to squashfs-root/
(
    cd "${BUILD_DIR}"
    "${PYTHON_APPIMAGE_CACHED}" --appimage-extract >/dev/null
    mv squashfs-root "${APPDIR}"
)

PYTHON_BIN="${APPDIR}/usr/bin/python${PY_MINOR}"
SITE_PACKAGES="${APPDIR}/usr/lib/python${PY_MINOR}/site-packages"
PIP="${PYTHON_BIN} -m pip"

# ---------------------------------------------------------------------------
# Install vibrante-node and its dependencies into the AppDir Python
# ---------------------------------------------------------------------------

log "Installing vibrante-node wheel into AppDir Python..."
${PIP} install --quiet --no-warn-script-location \
    "${WHEEL_PATH}" \
    -r "${APPIMAGE_DIR}/requirements-appimage.txt"

log "Installed packages:"
${PIP} list --format=columns | grep -E "^(vibrante|PyQt5|pydantic|toposort|QScintilla)" || true

# ---------------------------------------------------------------------------
# Set up AppDir structure
# ---------------------------------------------------------------------------

log "Configuring AppDir metadata..."

# AppRun — entry point (replaces the Python base AppImage's default AppRun)
cp "${APPIMAGE_DIR}/AppRun" "${APPDIR}/AppRun"
chmod +x "${APPDIR}/AppRun"

# Desktop entry
cp "${APPIMAGE_DIR}/vibrante-node.desktop" "${APPDIR}/vibrante-node.desktop"
# Also place it in usr/share/applications/ for XDG compliance
mkdir -p "${APPDIR}/usr/share/applications"
cp "${APPIMAGE_DIR}/vibrante-node.desktop" "${APPDIR}/usr/share/applications/vibrante-node.desktop"

# Application icon — AppImage convention: <name>.png at AppDir root
ICON_SRC="${REPO_ROOT}/icons/vibrante-node-resize_main_logo.png"
if [[ -f "${ICON_SRC}" ]]; then
    cp "${ICON_SRC}" "${APPDIR}/vibrante-node.png"
    # Also install to XDG icon dir (used by some desktop environments)
    mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
    cp "${ICON_SRC}" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/vibrante-node.png"
    log "Icon: ${ICON_SRC}"
else
    log "WARNING: icon not found at ${ICON_SRC} — AppImage will have no icon"
fi

# ---------------------------------------------------------------------------
# Build the AppImage
# ---------------------------------------------------------------------------

OUTPUT_APPIMAGE="${BUILD_DIR}/Vibrante-Node-${APP_VERSION}-x86_64.AppImage"
rm -f "${OUTPUT_APPIMAGE}"

log "Building AppImage..."

# SOURCE_DATE_EPOCH=0 makes squashfs timestamps reproducible.
# Inherit from environment if already set; otherwise default to 0.
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-0}"

ARCH=x86_64 "${APPIMAGETOOL}" "${APPDIR}" "${OUTPUT_APPIMAGE}"

# ---------------------------------------------------------------------------
# Verify and report
# ---------------------------------------------------------------------------

if [[ ! -f "${OUTPUT_APPIMAGE}" ]]; then
    err "appimagetool ran but output file not found: ${OUTPUT_APPIMAGE}"
fi

SIZE_MB="$(du -m "${OUTPUT_APPIMAGE}" | cut -f1)"
log ""
log "================================================================"
log "  AppImage built successfully!"
log "  Output : ${OUTPUT_APPIMAGE}"
log "  Size   : ${SIZE_MB} MB"
log "================================================================"
log ""
log "Quick test (requires a display or Xvfb):"
log "  QT_QPA_PLATFORM=offscreen ${OUTPUT_APPIMAGE} --help"
log ""
log "Install to your desktop (optional):"
log "  chmod +x ${OUTPUT_APPIMAGE}"
log "  mv ${OUTPUT_APPIMAGE} ~/Applications/"
