# Vibrante-Node — Linux Build Guide (Maintainers)

This document explains how to produce each Linux distribution artifact.
All commands assume you are at the **repo root** on an x86_64 Linux
machine (or WSL2 for the AppImage/deb steps).

---

## Prerequisites

### All artifacts

```bash
# Python 3.10+ with pip
python3 --version   # must be >= 3.10
pip3 --version

# Build tools
pip3 install build setuptools wheel
```

### AppImage only

```bash
# wget (for downloading base AppImage and appimagetool)
sudo apt install wget         # Ubuntu/Debian
sudo dnf install wget         # Fedora/Rocky
```

### .deb only

```bash
sudo apt install dpkg-dev     # Ubuntu/Debian only
```

---

## Step 0 — Build the Python wheel (required for all artifacts)

All Linux artifacts are built from the wheel, which bundles the Python
source and all data assets (nodes, icons, docs, workflows, etc.).

```bash
# From repo root
python -m build --wheel --no-isolation
# Output: dist/vibrante_node-<version>-py3-none-any.whl
```

The `setup.py` hook copies `nodes/`, `icons/`, `docs/`, `workflows/`,
`examples/`, `node_examples/`, and `plugins/` into the wheel's
`vibrante_node/` package directory at build time.

To also produce a source distribution (sdist):

```bash
python -m build --sdist --no-isolation
# Output: dist/vibrante_node-<version>.tar.gz
```

---

## Method 1 — PyPI wheel

Upload to PyPI with `twine` (maintainers only):

```bash
pip install twine
twine check dist/vibrante_node-*.whl dist/vibrante_node-*.tar.gz
twine upload dist/vibrante_node-*.whl dist/vibrante_node-*.tar.gz
```

For a test upload to TestPyPI:

```bash
twine upload --repository testpypi dist/vibrante_node-*.whl
pip install --index-url https://test.pypi.org/simple/ vibrante-node
```

---

## Method 2 — AppImage

**Must be run on a Linux x86_64 host.**  The script downloads the
Python 3.10 base AppImage and `appimagetool` automatically (cached
in `linux/build/cache/` after the first download).

```bash
bash linux/appimage/build_appimage.sh

# Specify a pre-built wheel explicitly:
bash linux/appimage/build_appimage.sh --wheel dist/vibrante_node-2.4.0-py3-none-any.whl

# Reproducible build (frozen timestamps):
SOURCE_DATE_EPOCH=0 bash linux/appimage/build_appimage.sh

# Output:
#   linux/build/Vibrante-Node-2.4.0-x86_64.AppImage
```

### What the script does

1. Downloads `appimagetool` into `linux/build/cache/` (if not cached).
2. Downloads `python3.10.14-cp310-cp310-manylinux2014_x86_64.AppImage`
   from the [python-appimage](https://github.com/niess/python-appimage)
   project (if not cached).
3. Extracts the Python AppImage to a temporary `AppDir`.
4. Runs `pip install` inside the AppDir's Python to install the
   `vibrante-node` wheel plus the extras in
   `linux/appimage/requirements-appimage.txt`.
5. Copies `AppRun`, `vibrante-node.desktop`, and the app icon into
   the AppDir.
6. Calls `appimagetool` to produce the final `.AppImage`.

### Reproducibility

`SOURCE_DATE_EPOCH=0` is set by default inside the script, making squashfs
timestamps deterministic.  For bit-for-bit identical packages, also pin
exact dependency versions.  After a successful build, capture the lock:

```bash
# Inside AppDir after a build
AppDir/usr/bin/python3.10 -m pip freeze > linux/appimage/requirements-appimage.lock
```

Then use the lock file in the script's `pip install` line for future
builds.

### System packages for AppImage builds

```bash
# Ubuntu 22.04+
sudo apt install wget fuse libfuse2

# Rocky Linux 9 / Alma
sudo dnf install wget fuse fuse-libs
```

---

## Method 3 — .deb package

**Must be run on Linux.**  Tested on Ubuntu 22.04 and 24.04.

```bash
bash linux/deb/build_deb.sh

# Specify wheel explicitly:
bash linux/deb/build_deb.sh --wheel dist/vibrante_node-2.4.0-py3-none-any.whl

# Specify version explicitly (if wheel filename differs):
bash linux/deb/build_deb.sh --version 2.4.0

# Output:
#   linux/build/vibrante-node_2.4.0_amd64.deb
```

### What the script does

1. Creates a staging directory under `linux/build/deb-staging/`.
2. Runs `pip install --target /opt/vibrante-node/lib` (inside the
   staging tree — does not touch the real filesystem).
3. Writes a shell launcher to `usr/bin/vibrante-node` that sets
   `PYTHONPATH=/opt/vibrante-node/lib` before calling `python3`.
4. Copies the desktop entry and icon.
5. Fills in `DEBIAN/control` from the template, substituting the
   version and calculated installed size.
6. Calls `dpkg-deb --build` to produce the `.deb`.

### Design decisions

- **System PyQt5 as a dependency** (not bundled): the `.deb` declares
  `Depends: python3-pyqt5` so it shares the system Qt5 libraries.
  This keeps the package small (~6 MB vs ~60 MB for a bundled Qt).
- **Installed to `/opt/`**: avoids conflicts with distro packages and
  makes uninstall clean.
- **No virtualenv**: the app runs under the system `python3` with
  `/opt/vibrante-node/lib` on `PYTHONPATH`.  If you need isolation,
  use the pip install method in a venv instead.

---

## Version bump checklist

When bumping the version (e.g., 2.4.0 → 2.4.0), update these files
**in addition** to the list in the root CLAUDE.md §10.18:

| File | What to change |
|------|----------------|
| `src/__init__.py` | `__version__ = "2.4.0"` |
| `vibrante_node/__init__.py` | `__version__ = "2.4.0"` |
| `pyproject.toml` | `version` in `[tool.setuptools.dynamic]` reads from `src.__version__` — no change needed here |
| `linux/appimage/requirements-appimage.txt` | Update if dependency minimums change |
| `linux/BUILDING.md` | Update version strings in examples |

After updating, rebuild all artifacts:

```bash
python -m build --wheel --no-isolation
SOURCE_DATE_EPOCH=0 bash linux/appimage/build_appimage.sh
bash linux/deb/build_deb.sh
```

---

## CI / testing

See `linux/ci/test_install.sh` for a smoke test that covers all three
install methods without requiring a display server.
