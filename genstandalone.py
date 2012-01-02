"""
generate a standalone python script including doit and its dependencies

Usage
======

This script should be executed on system where doit and dependencies are
installed. It also requires the the libraries "py" and "py.test". Then you
can distribute the stanalone script to other systems.

Note
=====

The generated standalone script can be used by any python version but the
dependencies included are dependent on the python version used to generate
the standalone script.
"""

import platform
import sys

import py
from _pytest.genscript import generate_script


def get_required_packages():
    # TODO: DRY, this was copied from setup.py
    platform_system = platform.system()
    install_requires = []

    # auto command dependencies to watch file-system
    if platform_system == "Darwin":
        install_requires.append('macfsevents')
    elif platform_system == "Linux":
        install_requires.append('pyinotify')

    # missing packages from stdlib for old versions
    if sys.version_info < (2, 6):
        install_requires.append('multiprocessing')
        install_requires.append('simplejson')

    return install_requires


def generate_doit_standalone(script_name='doit'):
    """create standalone doit script"""

    pkgs = get_required_packages()
    pkgs.append('doit')
    script = generate_script(
        'import sys; from doit.doit_cmd import cmd_main; sys.exit(cmd_main(sys.argv[1:]))',
        pkgs,
        )
    genscript = py.path.local(script_name)
    genscript.write(script)
    return 0


if __name__ == "__main__":
    generate_doit_standalone()

