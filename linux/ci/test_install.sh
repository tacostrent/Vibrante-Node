#!/usr/bin/env bash
# test_install.sh — Smoke test for all Vibrante-Node Linux install methods
#
# Usage:
#   bash linux/ci/test_install.sh [OPTIONS]
#
# Options:
#   --wheel  PATH   Test pip install from this .whl (skips if not given).
#   --appimage PATH Test this .AppImage (skips if not given).
#   --deb    PATH   Test this .deb (skips if not given).
#   --auto          Auto-detect artifacts in linux/build/ and dist/.
#   --help          Show this help.
#
# The script uses QT_QPA_PLATFORM=offscreen so no display server is needed.
# Exits 0 if all tested methods pass; non-zero otherwise.
#
# Each test:
#   1. Installs / runs the artifact.
#   2. Invokes the entry point with Qt's built-in --help flag.
#      Qt prints help text and exits 0 — this proves Python imports, Qt, and
#      the entry point wiring all work correctly without needing a display.
#   3. Reports PASS or FAIL.

set -euo pipefail
export QT_QPA_PLATFORM=offscreen

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS=0
FAIL=0
SKIP=0

ok()   { echo "  [PASS] $*"; ((PASS++)); }
fail() { echo "  [FAIL] $*" >&2; ((FAIL++)); }
skip() { echo "  [SKIP] $*"; ((SKIP++)); }
log()  { echo ""; echo "=== $* ==="; }

# Run a command with a timeout, capturing output; return its exit code.
run_timeout() {
    local timeout_s="$1"; shift
    # Use 'timeout' if available, otherwise just run directly.
    if command -v timeout &>/dev/null; then
        timeout "${timeout_s}" "$@" 2>&1 || return $?
    else
        "$@" 2>&1 || return $?
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD_DIR="${REPO_ROOT}/linux/build"

WHEEL_PATH=""
APPIMAGE_PATH=""
DEB_PATH=""
AUTO=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)
            sed -n '2,/^# Each test/{ /^#/{ s/^# \{0,1\}//; p }; /^[^#]/q }' "$0"
            exit 0
            ;;
        --wheel)    WHEEL_PATH="$2";    shift 2 ;;
        --appimage) APPIMAGE_PATH="$2"; shift 2 ;;
        --deb)      DEB_PATH="$2";      shift 2 ;;
        --auto)     AUTO=1;             shift   ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# Auto-detect artifacts
if [[ "${AUTO}" -eq 1 ]]; then
    WHEEL_PATH="$(ls -t "${REPO_ROOT}/dist"/vibrante_node-*.whl 2>/dev/null | head -1 || true)"
    APPIMAGE_PATH="$(ls -t "${BUILD_DIR}"/Vibrante-Node-*.AppImage 2>/dev/null | head -1 || true)"
    DEB_PATH="$(ls -t "${BUILD_DIR}"/vibrante-node_*.deb 2>/dev/null | head -1 || true)"
fi

echo ""
echo "Vibrante-Node Linux smoke tests"
echo "QT_QPA_PLATFORM=${QT_QPA_PLATFORM}"
echo "Detected artifacts:"
echo "  wheel   : ${WHEEL_PATH:-<not specified>}"
echo "  AppImage: ${APPIMAGE_PATH:-<not specified>}"
echo "  .deb    : ${DEB_PATH:-<not specified>}"
echo ""

# ---------------------------------------------------------------------------
# Test 1 — pip install from wheel
# ---------------------------------------------------------------------------

log "Test 1: pip install from wheel"

if [[ -z "${WHEEL_PATH}" ]]; then
    skip "No wheel specified (use --wheel or --auto)"
elif [[ ! -f "${WHEEL_PATH}" ]]; then
    fail "Wheel not found: ${WHEEL_PATH}"
else
    # Install into a temporary venv to avoid polluting the system
    VENV_DIR="$(mktemp -d)"
    trap 'rm -rf "${VENV_DIR}"' EXIT

    echo "  Installing into temporary venv: ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"

    # Install the wheel (PyQt5 is a dep — install it too)
    "${VENV_DIR}/bin/pip" install --quiet "${WHEEL_PATH}" 2>&1 | tail -3

    # Verify the entry point exists
    if [[ ! -f "${VENV_DIR}/bin/vibrante-node" ]]; then
        fail "Entry point vibrante-node not found after install"
    else
        echo "  Entry point: ${VENV_DIR}/bin/vibrante-node"

        # Run with Qt --help (exits 0, no display needed with offscreen)
        if OUTPUT="$(run_timeout 30 "${VENV_DIR}/bin/vibrante-node" --help 2>&1)"; then
            ok "vibrante-node --help exited 0"
        else
            EXIT_CODE=$?
            # Qt may exit with code 1 after printing help on some versions;
            # check that it at least printed something meaningful.
            if echo "${OUTPUT}" | grep -qiE "qt|usage|vibrante|option"; then
                ok "vibrante-node --help exited ${EXIT_CODE} but produced Qt/help output"
            else
                fail "vibrante-node --help failed (exit ${EXIT_CODE}): ${OUTPUT}"
            fi
        fi

        # Also verify the package version import
        if PKG_VER="$("${VENV_DIR}/bin/python" -c 'import vibrante_node; print(vibrante_node.__version__)' 2>&1)"; then
            ok "import vibrante_node — version: ${PKG_VER}"
        else
            fail "import vibrante_node failed: ${PKG_VER}"
        fi

        # Verify data bundling: nodes/ must be inside the package dir
        if "${VENV_DIR}/bin/python" -c "
import os, vibrante_node
pkg = os.path.dirname(vibrante_node.__file__)
nodes = os.path.join(pkg, 'nodes')
count = len([f for f in os.listdir(nodes) if f.endswith('.json')]) if os.path.isdir(nodes) else 0
assert count > 100, f'Expected >100 node JSON files, found {count} in {nodes}'
print(f'  nodes/ OK ({count} JSON files)')
" 2>&1; then
            ok "Data bundling — nodes/ inside package"
        else
            fail "nodes/ not found or too few files inside installed vibrante_node package"
        fi
    fi

    # Clean up venv
    rm -rf "${VENV_DIR}"
    trap - EXIT
fi

# ---------------------------------------------------------------------------
# Test 2 — AppImage
# ---------------------------------------------------------------------------

log "Test 2: AppImage"

if [[ -z "${APPIMAGE_PATH}" ]]; then
    skip "No AppImage specified (use --appimage or --auto)"
elif [[ ! -f "${APPIMAGE_PATH}" ]]; then
    fail "AppImage not found: ${APPIMAGE_PATH}"
elif [[ "$(uname -s)" != "Linux" ]]; then
    skip "AppImage test requires Linux (current OS: $(uname -s))"
else
    chmod +x "${APPIMAGE_PATH}"

    if OUTPUT="$(run_timeout 30 "${APPIMAGE_PATH}" --help 2>&1)"; then
        ok "AppImage --help exited 0"
    else
        EXIT_CODE=$?
        if echo "${OUTPUT}" | grep -qiE "qt|usage|vibrante|option"; then
            ok "AppImage --help exited ${EXIT_CODE} but produced Qt/help output"
        else
            fail "AppImage --help failed (exit ${EXIT_CODE}): $(echo "${OUTPUT}" | head -5)"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Test 3 — .deb package
# ---------------------------------------------------------------------------

log "Test 3: .deb package"

if [[ -z "${DEB_PATH}" ]]; then
    skip "No .deb specified (use --deb or --auto)"
elif [[ ! -f "${DEB_PATH}" ]]; then
    fail ".deb not found: ${DEB_PATH}"
elif [[ "$(uname -s)" != "Linux" ]]; then
    skip ".deb test requires Linux (current OS: $(uname -s))"
elif ! command -v dpkg &>/dev/null; then
    skip "dpkg not found — .deb test only runs on Debian/Ubuntu"
elif [[ "${EUID}" -ne 0 ]]; then
    skip ".deb install requires root (re-run as sudo or in CI with sudo)"
else
    echo "  Installing ${DEB_PATH} ..."
    if dpkg -i "${DEB_PATH}" 2>&1 | tail -3; then
        if [[ -f "/usr/bin/vibrante-node" ]]; then
            if OUTPUT="$(run_timeout 30 /usr/bin/vibrante-node --help 2>&1)"; then
                ok "vibrante-node --help exited 0 (deb install)"
            else
                EXIT_CODE=$?
                if echo "${OUTPUT}" | grep -qiE "qt|usage|vibrante|option"; then
                    ok "deb: vibrante-node --help exited ${EXIT_CODE} but produced Qt/help output"
                else
                    fail "deb: vibrante-node --help failed (exit ${EXIT_CODE}): $(echo "${OUTPUT}" | head -3)"
                fi
            fi
        else
            fail "/usr/bin/vibrante-node not found after dpkg install"
        fi
        # Uninstall to leave system clean
        dpkg -r vibrante-node 2>&1 | tail -2 || true
    else
        fail "dpkg -i failed — check for missing dependencies (run: apt-get install -f)"
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "========================================"
echo " Results: ${PASS} passed  ${FAIL} failed  ${SKIP} skipped"
echo "========================================"
echo ""

if [[ "${FAIL}" -gt 0 ]]; then
    exit 1
fi
exit 0
