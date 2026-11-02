"""
layers.py - Layers of AWS Lambda of Python and Pyjoyment
========================================================
::

    Usage: python layers.py COMMAND [OPTIONS]

      python layers.py matrix
      python layers.py build
      python layers.py build --python 3.14 --arch arm64

    Commands:
      build    Build the ZIP files of the layers in dist
      matrix   Print the versions of Python and the architectures of
               layers.toml as the matrix of a workflow of GitHub Actions

    Options of build:
      -a, --arch <name>        Architecture of the layer of Python, "arm64" or
                               "x86_64", all of layers.toml by default
      -p, --python <version>   Version of Python, as "3.14" or "3.14t", all of
                               layers.toml by default

The layers of the versions of Python and of the architectures of
``layers.toml``, which ``generate lambda-zip`` of Pyjoyment builds, with the
Pyjoyment of ``uv.lock``, in ``dist``: ``python3_14-arm64.zip``, Python for
one architecture, and ``pyjoyment-python3_14.zip``, Pyjoyment for both, which
is the same for both, so the build of each architecture writes it.
"""

import Pyjo.Exception
import Pyjo.JSON

from Pyjo.Util import extract_usage, getopt

import os
import shutil
import subprocess
import sys
import tempfile
import tomllib


HOME = os.path.dirname(os.path.abspath(__file__))


def config() -> dict[str, list[str]]:
    with open(os.path.join(HOME, 'layers.toml'), 'rb') as file:
        return tomllib.load(file)


def python_layer(python: str, arch: str) -> str:
    return f'python{python.replace(".", "_")}-{arch}'


def pyjoyment_layer(python: str) -> str:
    return f'pyjoyment-python{python.replace(".", "_")}'


def matrix() -> dict[str, list[dict[str, str]]]:
    layers = config()
    return {'include': [{'python': p, 'arch': a} for p in layers['python'] for a in layers['architectures']]}


# generate lambda-zip writes the ZIP files of the application of the current directory, so it runs in a directory of its
# own with pyproject.toml and uv.lock only, whose function.zip is left there
def build(python: str, arch: str, dist: str) -> list[str]:
    os.makedirs(dist, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name in ('pyproject.toml', 'uv.lock'):
            shutil.copyfile(os.path.join(HOME, name), os.path.join(tmp, name))
        command = [sys.executable, '-m', 'Pyjoyment', 'generate', 'lambda-zip', '--python', python, '--arch', arch]
        if (code := subprocess.run(command, cwd=tmp, stdout=subprocess.DEVNULL).returncode) != 0:
            raise Pyjo.Exception.new(f'Command "generate lambda-zip" failed with exit status {code}')
        files = {'python.zip': python_layer(python, arch), 'pyjoyment.zip': pyjoyment_layer(python)}
        paths = [os.path.join(dist, f'{layer}.zip') for layer in files.values()]
        for (name, _), path in zip(files.items(), paths, strict=True):
            shutil.move(os.path.join(tmp, 'dist', name), path)
    return paths


def main(argv: list[str]) -> None:
    command, arguments = (argv[0], argv[1:]) if argv else ('', [])
    if command == 'matrix' and not arguments:
        print(Pyjo.JSON.to_json(matrix()))
    elif command == 'build' and (opts := getopt(arguments, {'a|arch=s': None, 'p|python=s': None})) and not arguments:
        layers = config()
        for python in [opts.python] if opts.python else layers['python']:
            for arch in [opts.arch] if opts.arch else layers['architectures']:
                for path in build(python, arch, os.path.join(HOME, 'dist')):
                    print(f'  [write] {path}')
    else:
        raise SystemExit(extract_usage())


if __name__ == '__main__':
    main(sys.argv[1:])
