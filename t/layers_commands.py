import layers

from Pyjo.Test import *

import contextlib
import io
import re


# The layers of layers.toml

with subtest('Names'):
    is_ok(layers.python_layer('3.14', 'arm64'), 'python3_14-arm64', 'layer of Python')
    is_ok(layers.python_layer('3.14t', 'x86_64'), 'python3_14t-x86_64', 'layer of a free-threaded Python')
    is_ok(layers.pyjoyment_layer('3.14'), 'pyjoyment-python3_14', 'layer of Pyjoyment')
    is_ok(layers.pyjoyment_layer('3.14t'), 'pyjoyment-python3_14t', 'layer of Pyjoyment of a free-threaded Python')
    config = layers.config()
    for name in (*map(layers.pyjoyment_layer, config['python']), layers.python_layer(config['python'][0], 'x86_64')):
        like_ok(name, re.compile(r'^[A-Za-z0-9_-]+$'), f'{name} is a name that Lambda takes')

with subtest('Matrix'):
    config = layers.config()
    include = layers.matrix()['include']
    is_ok(len(include), len(config['python']) * len(config['architectures']), 'every version on every architecture')
    is_ok(include[0], {'python': config['python'][0], 'arch': config['architectures'][0]}, 'first of them')
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        layers.main(['matrix'])
    like_ok(output.getvalue(), re.compile(r'^\{"include":\[\{"python":"3\.\d+t?","arch":"\w+"\}'), 'matrix in JSON')

with subtest('Usage'):
    for argv in ([], ['unknown'], ['matrix', 'extra'], ['build', '--unknown'], ['build', 'extra']):
        try:
            layers.main(argv)
            usage = None
        except SystemExit as e:
            usage = e.code
        like_ok(usage, re.compile(r'^Usage: python layers\.py COMMAND'), f'usage of {argv}')

done_testing()
