"""
Custom setuptools build hook for Vibrante-Node.

When building a wheel, this hook copies all read-only data assets
(nodes/, icons/, docs/, etc.) from the project root into the
vibrante_node/ package directory inside the build tree.

The pip-installed entry point (vibrante_node/app.py) detects the presence
of nodes/ inside its own package directory and patches resource_path()
accordingly.  Nothing is written to the source tree — all copies go to
the temporary build_lib/ directory that setuptools hands to bdist_wheel.

Development / editable installs are unaffected: the data lives at the
project root, and resource_path() resolves there naturally.
"""
import os
import shutil
from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

# Directories at the project root that must be bundled inside vibrante_node/
_DATA_DIRS = [
    'nodes',
    'icons',
    'docs',
    'workflows',
    'examples',
    'node_examples',
    'plugins',
]

# Individual files at the project root to bundle
_DATA_FILES = [
    'splash.png',
    'logo.png',
    'LICENSE',
]


class build_py(_build_py):
    """Extended build_py that bundles runtime data into the wheel."""

    def run(self):
        super().run()
        pkg_dest = os.path.join(self.build_lib, 'vibrante_node')
        os.makedirs(pkg_dest, exist_ok=True)

        for dir_name in _DATA_DIRS:
            src = dir_name
            dst = os.path.join(pkg_dest, dir_name)
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                print(f'vibrante-node build: bundled {dir_name}/ -> vibrante_node/{dir_name}/')

        for file_name in _DATA_FILES:
            if os.path.isfile(file_name):
                shutil.copy2(file_name, pkg_dest)
                print(f'vibrante-node build: bundled {file_name} -> vibrante_node/{file_name}')


setup(cmdclass={'build_py': build_py})
