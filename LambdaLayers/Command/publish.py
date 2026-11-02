"""
LambdaLayers.Command.publish - Publish command
==============================================
::

    Usage: APPLICATION publish [OPTIONS]

      python layers.py publish
      python layers.py publish --python 3.14 --arch arm64
      python layers.py publish --apply

    Options:
      -a, --arch <name>        Architecture of the layer of Python, "arm64" or
                               "x86_64", all of layers.toml by default
          --apply              Publish, where the command only shows what it
                               would do by default
      -h, --help               Show this summary of available options
      -p, --python <version>   Version of Python, as "3.14" or "3.14t", all of
                               layers.toml by default

:mod:`LambdaLayers.Command.publish` compares the files of ``dist``, which
:mod:`LambdaLayers.Command.build` writes, with the latest versions of their
layers in every region that the account has enabled, but the
``excluded_regions`` of ``layers.toml``, and shows what it would
publish. With ``--apply``, it publishes the files that differ, makes the
latest versions public, and writes the ARNs of the latest versions of each
layer in its regions in ``dist``, as ``python3_14-arm64.json``.

A region that fails, as one that does not answer, is shown as ``[error]``
with its error, the others go on, and the command fails at its end.

The requests to the APIs of AWS are signed with :mod:`Pyjo.AWS.SigV4`, with
the credentials of the environment.
"""

import LambdaLayers
import Pyjo.Exception
import Pyjo.JSON
import Pyjoyment.Command

from Pyjo.Util import extract_usage, getopt

import os


class LambdaLayers_Command_publish(Pyjoyment.Command.object):
    """
    :mod:`LambdaLayers.Command.publish` inherits all attributes and methods
    from :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Publish the layers of dist that differ, with --apply'

    usage = extract_usage()

    endpoint = LambdaLayers.ENDPOINT
    """::

        endpoint = publish.endpoint
        publish.endpoint = '/{region}/{service}'

    The URL of the APIs of AWS, with the placeholders ``service`` and
    ``region``, which a test serves itself.
    """

    def run(self, *args: str) -> None:
        """::

            publish.run(*sys.argv[1:])

        Run this command.
        """
        arguments = list(args)
        if not (opts := getopt(arguments, {'a|arch=s': None, 'apply': None, 'p|python=s': None})) or arguments:
            raise Pyjo.Exception.new(self.usage)
        dist = self.app.home.child('dist')
        config = self.app.config()
        selected = LambdaLayers.publications(config, opts.python, opts.arch)
        for name, _ in selected:
            if not os.path.isfile(dist.child(f'{name}.zip')):
                raise Pyjo.Exception.new(f'No file of the layer {name} in dist, which the command build writes')

        # A layer of Python goes to a region far away in one request
        ua = self.app.ua
        ua.inactivity_timeout = 300
        excluded = config.get('excluded_regions', [])
        regions = [region for region in LambdaLayers.regions(ua, self.endpoint) if region not in excluded]
        failed: list[str] = []
        for name, params in selected:
            path = dist.child(f'{name}.zip')
            arns: dict[str, str | None] = {}
            for region, action, arn in LambdaLayers.publish(
                ua, regions, name, params, path, bool(opts.apply), self.endpoint
            ):
                self._loud(f'  [{action}] {region} {name} {arn or ""}'.rstrip())
                if action == 'error':
                    failed.append(f'{region} {name}')
                else:
                    arns[region] = arn
            if opts.apply:
                dist.child(f'{name}.json').spew(Pyjo.JSON.to_json(arns, sort_keys=True) + '\n')

        # A region that fails leaves the others to the end, and the command fails then
        if failed:
            raise Pyjo.Exception.new(f'Failed in {len(failed)} of the regions: {", ".join(failed)}')


new = LambdaLayers_Command_publish.new
object = LambdaLayers_Command_publish
