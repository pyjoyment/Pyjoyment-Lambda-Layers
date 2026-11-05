"""
LambdaLayers.Command.index - Index command
==========================================
::

    Usage: APPLICATION index [OPTIONS] DIR

      python layers.py index arns
      python layers.py index --latest latest.json --notes notes.md arns

    Options:
      -h, --help            Show this summary of available options
      -l, --latest <file>   Index of the latest release, which the new versions
                            are of
      -n, --notes <file>    Notes of a release, written when the index has new
                            versions
      -o, --output <file>   Index of the layers, defaults to "layers.json"

:mod:`LambdaLayers.Command.index` merges the ARNs of the layers that
:mod:`LambdaLayers.Command.publish` writes, one file of each layer in a
directory, into the index of the layers, ``{layer: {region: arn}}``, with its
keys sorted, so that the same layers give the same file. With ``--latest``,
it compares the index with the one of the latest release, and with
``--notes``, it writes the notes of a release with the new versions, only when
there are some, which tells the workflow to release.
"""

import LambdaLayers
import Pyjo.Exception
import Pyjo.File
import Pyjo.JSON
import Pyjoyment.Command

from Pyjo.Util import extract_usage, getopt

from typing import Any


class LambdaLayers_Command_index(Pyjoyment.Command.object):
    """
    :mod:`LambdaLayers.Command.index` inherits all attributes and methods
    from :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Merge the ARNs of the layers into their index'

    usage = extract_usage()

    def run(self, *args: str) -> None:
        """::

            index.run(*sys.argv[1:])

        Run this command.
        """
        arguments = list(args)
        opts = getopt(arguments, {'l|latest=s': None, 'n|notes=s': None, 'o|output=s': None})
        if not opts or len(arguments) != 1:
            raise Pyjo.Exception.new(self.usage)
        log = self.app.log

        index = LambdaLayers.index(Pyjo.File.path(arguments[0]))
        output = Pyjo.File.path(opts.output or 'layers.json')
        output.spew(Pyjo.JSON.to_json(index, sort_keys=True) + '\n')
        log.info(f'[write] {output}')
        if not opts.latest:
            return

        latest: Any = Pyjo.JSON.decode_json(Pyjo.File.path(opts.latest).slurp())
        if not (versions := LambdaLayers.new_versions(index, latest)):
            log.info('[same] the layers of the latest release')
            return
        for layer, numbers in versions.items():
            log.info(f'[new] {layer} {", ".join(map(str, numbers))}')
        if opts.notes:
            lines = [f'- `{layer}`: version {", ".join(map(str, numbers))}' for layer, numbers in versions.items()]
            notes = Pyjo.File.path(opts.notes)
            notes.spew('The layers with new versions:\n\n' + '\n'.join(lines) + '\n')
            log.info(f'[write] {notes}')


new = LambdaLayers_Command_index.new
object = LambdaLayers_Command_index
