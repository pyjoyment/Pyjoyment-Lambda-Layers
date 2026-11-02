"""
layers.py - Layers of AWS Lambda of Python and Pyjoyment
========================================================
::

    python layers.py build --python 3.14 --arch arm64
    python layers.py publish --python 3.14 --arch arm64
    python layers.py publish --apply

The application of the commands of :mod:`LambdaLayers`, ``build``, ``matrix``
and ``publish``, with the configuration of ``layers.toml``.
"""

from Pyjoyment.Lite import *


plugin('TOMLConfig')
app.commands.namespaces.append('LambdaLayers.Command')

app.start()
