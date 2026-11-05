"""
LambdaLayers.Command.build - Build command
==========================================
::

    Usage: APPLICATION build [OPTIONS]

      python layers.py build
      python layers.py build --python 3.14 --arch arm64

    Options:
      -a, --arch <name>        Architecture of the layer of Python, "arm64" or
                               "x86_64", all of layers.toml by default
      -h, --help               Show this summary of available options
      -p, --python <version>   Version of Python, as "3.14" or "3.14t", all of
                               layers.toml by default

:mod:`LambdaLayers.Command.build` builds the layers in ``dist``, with
``generate lambda-zip`` of Pyjoyment and the Pyjoyment and Pyjo-AWS of
``uv.lock``, as ``python3_14-arm64.zip`` and ``pyjoyment-python3_14.zip``,
which it logs in the log of the application. It fails if the layer of
Pyjoyment has no Pyjo-AWS.
"""

import LambdaLayers
import Pyjo.Exception
import Pyjoyment.Command

from Pyjo.Util import extract_usage, getopt


class LambdaLayers_Command_build(Pyjoyment.Command.object):
    """
    :mod:`LambdaLayers.Command.build` inherits all attributes and methods
    from :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Build the ZIP files of the layers in dist'

    usage = extract_usage()

    def run(self, *args: str) -> None:
        """::

            build.run(*sys.argv[1:])

        Run this command.
        """
        arguments = list(args)
        if not (opts := getopt(arguments, {'a|arch=s': None, 'p|python=s': None})) or arguments:
            raise Pyjo.Exception.new(self.usage)
        config = self.app.config()
        home = self.app.home
        for python in [opts.python] if opts.python else config['python']:
            for arch in [opts.arch] if opts.arch else config['architectures']:
                for path in LambdaLayers.build(home, python, arch, home.child('dist')):
                    self.app.log.info(f'[write] {path}')


new = LambdaLayers_Command_build.new
object = LambdaLayers_Command_build
