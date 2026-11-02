import LambdaLayers
import LambdaLayers.Command.publish
import Pyjo.File
import Pyjo.Server
import Pyjoyment

from Pyjo.Test import *

import base64
import contextlib
import hashlib
import io
import os
import re


# The commands of layers.py, with the APIs of AWS of an application of the test

app = Pyjo.Server.new().load_app(Pyjo.File.curfile().dirname().sibling('layers.py'))
app.log.level = 'fatal'
config = app.config()


def run(*args, command=None):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        (command or app.commands).run(*args)
    return output.getvalue()


def digest(content):
    return base64.b64encode(hashlib.sha256(content).digest()).decode()


with subtest('Names'):
    is_ok(LambdaLayers.python_layer('3.14', 'arm64'), 'python3_14-arm64', 'layer of Python')
    is_ok(LambdaLayers.python_layer('3.14t', 'x86_64'), 'python3_14t-x86_64', 'layer of a free-threaded Python')
    is_ok(LambdaLayers.pyjoyment_layer('3.14'), 'pyjoyment-python3_14', 'layer of Pyjoyment')
    for name, _ in LambdaLayers.publications(config, None, None):
        like_ok(name, re.compile(r'^[A-Za-z0-9_-]+$'), f'{name} is a name that Lambda takes')

with subtest('Matrix'):
    include = LambdaLayers.matrix(config)['include']
    is_ok(len(include), len(config['python']) * len(config['architectures']), 'every version on every architecture')
    is_ok(include[0], {'python': config['python'][0], 'arch': config['architectures'][0]}, 'first of them')
    like_ok(run('matrix'), re.compile(r'^\{"include":\[\{"python":"3\.\d+t?","arch":"\w+"\}'), 'matrix in JSON')
    throws_ok(lambda: run('matrix', 'extra'), re.compile(r'^Usage: APPLICATION matrix'), 'usage')

with subtest('Publications'):
    first, second = config['architectures'][:2]
    is_ok(
        LambdaLayers.publications(config, '3.14', first),
        [
            (
                'python3_14-' + first,
                {
                    'Description': 'Python 3.14 of python-build-standalone',
                    'CompatibleRuntimes': ['provided.al2023'],
                    'CompatibleArchitectures': [first],
                    'LicenseInfo': 'PSF-2.0',
                },
            ),
            (
                'pyjoyment-python3_14',
                {
                    'Description': LambdaLayers.publications(config, '3.14', first)[1][1]['Description'],
                    'CompatibleRuntimes': ['provided.al2023', 'python3.14'],
                    'CompatibleArchitectures': config['architectures'],
                    'LicenseInfo': 'Artistic-2.0',
                },
            ),
        ],
        'layers of the first architecture',
    )
    like_ok(
        LambdaLayers.publications(config, '3.14', first)[1][1]['Description'],
        re.compile(r'^Pyjoyment \S+ for Python 3\.14$'),
        'version of Pyjoyment',
    )
    is_ok([name for name, _ in LambdaLayers.publications(config, '3.14', second)], ['python3_14-' + second], 'second')
    is_ok(
        LambdaLayers.publications(config, '3.14t', first)[1][1]['CompatibleRuntimes'],
        ['provided.al2023'],
        'no runtime of Lambda for a free-threaded Python',
    )
    is_ok(
        len(LambdaLayers.publications(config, None, None)),
        len(config['python']) * (len(config['architectures']) + 1),
        'all of them',
    )

with subtest('Usage'):
    for args in (('build', '--unknown'), ('build', 'extra'), ('publish', '--unknown'), ('publish', 'extra')):
        with contextlib.redirect_stderr(io.StringIO()):
            throws_ok(lambda args=args: run(*args), re.compile(rf'^Usage: APPLICATION {args[0]}'), f'usage of {args}')

# The APIs of AWS: two regions, the second of them on the next page, and the versions of the layers, one on each page,
# with the requests and their credential scopes
versions = {}
public = set()
policies = []
requests = []
aws = Pyjoyment.new()
aws.log.level = 'fatal'
aws.hook(
    'before_dispatch', lambda c: requests.append((c.req.method, c.req.url.path.to_str(), c.req.headers.authorization))
)


def list_regions(c):
    if c.req.json().get('NextToken') == 'next':
        return c.render(json={'Regions': [{'RegionName': 'eu-central-1', 'RegionOptStatus': 'ENABLED'}]})
    c.render(
        json={'Regions': [{'RegionName': 'us-east-1', 'RegionOptStatus': 'ENABLED_BY_DEFAULT'}], 'NextToken': 'next'}
    )


def list_versions(c):
    if (layer := versions.get((c.param('region'), c.param('layer')))) is None:
        c.res.headers.header('X-Amzn-ErrorType', 'ResourceNotFoundException')
        return c.render(json={'Type': 'User', 'message': 'Layer not found'}, status=404)
    index = int(c.param('Marker') or 0)
    page = {'LayerVersions': [{'Version': v['Version']} for v in layer[index : index + 1]]}
    c.render(json={**page, **({'NextMarker': str(index + 1)} if index + 1 < len(layer) else {})})


def get_version(c):
    layer = versions[(c.param('region'), c.param('layer'))]
    c.render(json=next(v for v in layer if v['Version'] == int(c.param('version'))))


def publish_version(c):
    region, name = c.param('region'), c.param('layer')
    layer = versions.setdefault((region, name), [])
    body = c.req.json()
    version = {
        'Version': len(layer) + 1,
        'LayerVersionArn': f'arn:aws:lambda:{region}:959435416781:layer:{name}:{len(layer) + 1}',
        'Content': {'CodeSha256': digest(base64.b64decode(body['Content']['ZipFile']))},
        **{k: v for k, v in body.items() if k != 'Content'},
    }
    layer.append(version)
    c.render(json=version, status=201)


def add_permission(c):
    key = (c.param('region'), c.param('layer'), c.param('version'))
    if key in public:
        c.res.headers.header('X-Amzn-ErrorType', 'ResourceConflictException')
        return c.render(
            json={'Type': 'User', 'message': 'The statement id (public) provided already exists'}, status=409
        )
    policies.append(c.req.json())
    public.add(key)
    c.render(json={'Statement': '{}'}, status=201)


aws.routes.post('/us-east-1/account/listRegions').to(cb=list_regions)
aws.routes.get('/<region>/lambda/2018-10-31/layers/<layer>/versions').to(cb=list_versions)
aws.routes.post('/<region>/lambda/2018-10-31/layers/<layer>/versions').to(cb=publish_version)
aws.routes.get('/<region>/lambda/2018-10-31/layers/<layer>/versions/<version>').to(cb=get_version)
aws.routes.post('/<region>/lambda/2018-10-31/layers/<layer>/versions/<version>/policy').to(cb=add_permission)
aws.routes.get('/<region>/lambda/fail').to(
    cb=lambda c: (
        c.res.headers.header('X-Amzn-ErrorType', 'ValidationException:http://internal.amazon.com/')
        and c.render(json={'message': 'Bad request'}, status=400)
    )
)
app.ua.server.app = aws

environ = dict(os.environ)
os.environ.update(AWS_ACCESS_KEY_ID='AKIDEXAMPLE', AWS_SECRET_ACCESS_KEY='secret', AWS_SESSION_TOKEN='token')
home = app.home
app.home = Pyjo.File.tempdir()
publish = LambdaLayers.Command.publish.new()
publish.app = app
publish.endpoint = '/{region}/{service}'
dist = app.home.child('dist').make_path()
python, layer = f'python3_14-{config["architectures"][0]}', 'pyjoyment-python3_14'
dist.child(f'{python}.zip').spew(b'python')
dist.child(f'{layer}.zip').spew(b'pyjoyment')
arn = f'arn:aws:lambda:us-east-1:959435416781:layer:{layer}'
versions[('us-east-1', layer)] = [
    {'Version': 2, 'LayerVersionArn': f'{arn}:2', 'Content': {'CodeSha256': digest(b'pyjoyment')}},
    {'Version': 1, 'LayerVersionArn': f'{arn}:1', 'Content': {'CodeSha256': digest(b'older')}},
]

with subtest('Dry run'):
    output = run('--python', '3.14', '--arch', config['architectures'][0], command=publish)
    is_ok(
        output.splitlines(),
        [
            f'  [would publish] eu-central-1 {python}',
            f'  [would publish] us-east-1 {python}',
            f'  [would publish] eu-central-1 {layer}',
            f'  [keep] us-east-1 {layer} {arn}:2',
        ],
        'what it would do, with the latest version on the second page',
    )
    is_ok([r for r in requests if r[0] == 'POST' and 'lambda' in r[1]], [], 'nothing published')
    ok(not os.path.exists(dist.child(f'{python}.json')), 'no ARNs')
    for method, path, authorization in requests:
        region, service = path.split('/')[1:3]
        like_ok(authorization, re.compile(rf'/{region}/{service}/aws4_request, '), f'{method} {path} signed')

with subtest('Apply'):
    requests.clear()
    output = run('--python', '3.14', '--arch', config['architectures'][0], '--apply', command=publish)
    is_ok(
        output.splitlines(),
        [
            f'  [publish] eu-central-1 {python} arn:aws:lambda:eu-central-1:959435416781:layer:{python}:1',
            f'  [publish] us-east-1 {python} arn:aws:lambda:us-east-1:959435416781:layer:{python}:1',
            f'  [publish] eu-central-1 {layer} arn:aws:lambda:eu-central-1:959435416781:layer:{layer}:1',
            f'  [keep] us-east-1 {layer} {arn}:2',
        ],
        'published',
    )
    published = versions[('eu-central-1', layer)][0]
    is_ok(published['CompatibleRuntimes'], ['provided.al2023', 'python3.14'], 'runtimes')
    is_ok(published['LicenseInfo'], 'Artistic-2.0', 'license')
    is_ok(published['Content']['CodeSha256'], digest(b'pyjoyment'), 'content')
    is_ok(
        public,
        {
            ('eu-central-1', python, '1'),
            ('us-east-1', python, '1'),
            ('eu-central-1', layer, '1'),
            ('us-east-1', layer, '2'),
        },
        'public, also the version that was kept',
    )
    is_ok(
        policies[0],
        {'StatementId': 'public', 'Action': 'lambda:GetLayerVersion', 'Principal': '*'},
        'policy for everyone',
    )
    is_ok(
        dist.child(f'{layer}.json').slurp().decode(),
        f'{{"eu-central-1":"arn:aws:lambda:eu-central-1:959435416781:layer:{layer}:1","us-east-1":"{arn}:2"}}\n',
        'ARNs',
    )
    output = run('--python', '3.14', '--arch', config['architectures'][0], '--apply', command=publish)
    is_ok([line.split()[0] for line in output.splitlines()], ['[keep]'] * 4, 'nothing more to publish, already public')

with subtest('Errors'):
    throws_ok(
        lambda: LambdaLayers.aws(app.ua, 'GET', 'lambda', 'us-east-1', '/fail', endpoint='/{region}/{service}'),
        re.compile(r'^GET /us-east-1/lambda/fail: 400 ValidationException: Bad request'),
        'error of AWS',
    )
    throws_ok(
        lambda: run('--python', '3.15', command=publish),
        re.compile(r'^No file of the layer python3_15-\w+ in dist'),
        'no file',
    )

os.environ.clear()
os.environ.update(environ)
app.home = home

done_testing()
