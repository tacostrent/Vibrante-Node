# Vibrante-Node — Linux Installation Guide

Choose the method that fits your situation:

| Method | Best for | Requires |
|--------|----------|----------|
| [pip (PyPI)](#method-1-pip-recommended) | Developers, Houdini/Prism users, pipelines | Python 3.10+ |
| [AppImage](#method-2-appimage) | Quick try-out, no Python setup | Just the file |
| [.deb package](#method-3-deb-ubuntu--debian) | Ubuntu/Debian system installs | sudo |

---

## Method 1: pip (Recommended)

Works on any distro with Python 3.10+.  Integrates with your existing
Python environment, so the Houdini bridge and Prism plugins can import
your studio's libraries.

### Ubuntu 22.04 / 24.04

```bash
# Ensure Python 3.10+ and system PyQt5 are available
sudo apt install python3 python3-pip python3-pyqt5

# Install Vibrante-Node
pip install vibrante-node

# Launch
vibrante-node
```

### Rocky Linux 9 / AlmaLinux 9

> **Note:** Rocky 9's default Python is 3.9.  Install 3.11 (the VFX
> Reference Platform version) from EPEL or the Python 3 Software
> Collections before continuing.

```bash
# Enable EPEL and install Python 3.11
sudo dnf install epel-release
sudo dnf install python3.11 python3.11-pip

# Install Vibrante-Node under Python 3.11
python3.11 -m pip install vibrante-node

# Launch
vibrante-node
```

### Fedora 40+

```bash
pip install vibrante-node
vibrante-node
```

### Optional extras

```bash
# Add the full QScintilla code editor (syntax highlighting + autocomplete)
pip install "vibrante-node[editor]"

# Add Gemini AI chat integration
pip install "vibrante-node[ai]"

# Everything at once
pip install "vibrante-node[all]"
```

### Wayland note (Ubuntu 24.04 / Fedora 40+)

PyQt5's Wayland backend is fragile.  If the app crashes on startup, force X11:

```bash
QT_QPA_PLATFORM=xcb vibrante-node
```

To make this permanent, add the following to `~/.bashrc` or `~/.profile`:

```bash
export QT_QPA_PLATFORM=xcb
```

---

## Method 2: AppImage

A single self-contained file.  No installation needed — just download,
mark executable, and run.  Works on Ubuntu 22.04+, Rocky Linux 9+, and
most other modern x86_64 distros.

### Download and run

```bash
# Download the latest release
wget https://github.com/KamalTDev/vibrante-node/releases/latest/download/Vibrante-Node-2.4.0-x86_64.AppImage

# Mark executable
chmod +x Vibrante-Node-2.4.0-x86_64.AppImage

# Run
./Vibrante-Node-2.4.0-x86_64.AppImage
```

### Optional: integrate with your desktop

```bash
# Move to a permanent location
mv Vibrante-Node-2.4.0-x86_64.AppImage ~/Applications/

# (Optional) add a desktop launcher — most desktop envs pick this up
cp ~/.local/share/applications/  # some AppImage launchers do this automatically
```

> **Wayland:** The AppImage defaults to `QT_QPA_PLATFORM=xcb`.  If you
> want to test the Wayland backend, set `QT_QPA_PLATFORM=wayland` before
> launching.

### Rocky Linux 9 — FUSE requirement

AppImages need FUSE 2 at runtime:

```bash
sudo dnf install fuse fuse-libs
```

If FUSE is unavailable, you can extract and run without it:

```bash
./Vibrante-Node-2.4.0-x86_64.AppImage --appimage-extract
./squashfs-root/AppRun
```

---

## Method 3: .deb (Ubuntu / Debian)

Pre-built `.deb` for Ubuntu 22.04 (jammy) and 24.04 (noble).
Uses the system `python3-pyqt5` package — lighter than the AppImage.

### Install

```bash
# Download the .deb
wget https://github.com/KamalTDev/vibrante-node/releases/latest/download/vibrante-node_2.4.0_amd64.deb

# Install
sudo dpkg -i vibrante-node_2.4.0_amd64.deb

# Satisfy any missing dependencies (if dpkg reports errors)
sudo apt-get install -f

# Launch
vibrante-node
```

### Uninstall

```bash
sudo dpkg -r vibrante-node
```

---

## Troubleshooting

### "Could not connect to display" / blank window on startup

Force X11 mode:

```bash
QT_QPA_PLATFORM=xcb vibrante-node
```

If you are running in a desktop session without Xwayland, install it:

```bash
# Ubuntu
sudo apt install xwayland

# Fedora / Rocky
sudo dnf install xorg-x11-server-Xwayland
```

### "libxcb-icccm.so.4: cannot open shared object file"

Install the missing xcb library:

```bash
# Ubuntu / Debian
sudo apt install libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0

# Fedora / Rocky
sudo dnf install xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil
```

### Houdini bridge: SELinux blocking the TCP connection (Rocky / Alma)

The Houdini bridge connects on TCP port 18811 (localhost only).  If you
see `ConnectionRefusedError` and SELinux is in enforcing mode, allow it:

```bash
sudo setsebool -P nis_enabled 1
# or, more precisely:
sudo semanage port -a -t http_port_t -p tcp 18811
```

### "ImportError: No module named PyQt5" (pip install)

The `vibrante-node` pip package declares `PyQt5` as a dependency, but on
some distros pip cannot build the Qt platform plugin from source.  Install
the system package instead and link it into your virtual environment:

```bash
# Ubuntu
sudo apt install python3-pyqt5
pip install --no-deps vibrante-node   # skip PyQt5, use system one
```

### AppImage runs but no Houdini/Prism nodes appear

The AppImage has no access to your studio's Python libraries.  Use the
**pip install** method instead — it runs inside your own Python interpreter
where Prism, houdini, and studio packages are importable.

---

## User data location

Vibrante-Node stores your custom nodes and workflows in:

```
~/.local/share/vibrante-node/
```

This directory is created automatically on first launch.  Back it up
regularly — it is NOT managed by the package manager.
