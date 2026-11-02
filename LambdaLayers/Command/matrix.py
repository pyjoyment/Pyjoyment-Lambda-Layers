"""
LambdaLayers.Command.matrix - Matrix command
============================================
::

    Usage: APPLICATION matrix [OPTIONS]

      python layers.py matrix

    Options:
      -h, --help   Show this summary of available options

:mod:`LambdaLayers.Command.matrix` prints the versions of Python and the
architectures of ``layers.toml`` as the matrix of a workflow of GitHub
Actions, in JSON, one job for each version and architecture.
"""

import LambdaLayers
import Pyjo.Exception
import Pyjo.JSON
import Pyjoyment.Command

from Pyjo.Util import extract_usage


class LambdaLayers_Command_matrix(Pyjoyment.Command.object):
    """
    :mod:`LambdaLayers.Command.matrix` inherits all attributes and methods
    from :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Print the layers of layers.toml as a matrix of GitHub Actions'

    usage = extract_usage()

    def run(self, *args: str) -> None:
        """::

            matrix.run(*sys.argv[1:])

        Run this command.
        """
        if args:
            raise Pyjo.Exception.new(self.usage)
        print(Pyjo.JSON.to_json(LambdaLayers.matrix(self.app.config())))


new = LambdaLayers_Command_matrix.new
object = LambdaLayers_Command_matrix
