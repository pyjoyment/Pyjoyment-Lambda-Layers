import LambdaLayers
import LambdaLayers.Command.index
import LambdaLayers.Command.publish
import Pyjo.File
import Pyjo.Server
import Pyjoyment

from Pyjo.Test import *
from Pyjo.Util import b64_decode, b64_encode, sha256_bytes

import contextlib
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
    return b64_encode(sha256_bytes(content), '')


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
callers = []
broken = set()
policies = []
requests = []
aws = Pyjoyment.new()
aws.log.level = 'fatal'
aws.hook(
    'before_dispatch', lambda c: requests.append((c.req.method, c.req.url.path.to_str(), c.req.headers.authorization))
)


IDENTITY = 'arn:aws:sts::959435416781:assumed-role/Pyjoyment-Lambda-Layers-dry-run/test'


def caller_identity(c):
    callers.append((c.param('Action'), c.param('Version'), c.req.headers.accept))
    result = {'Account': '959435416781', 'Arn': IDENTITY, 'UserId': 'AROAEXAMPLE:test'}
    c.render(json={'GetCallerIdentityResponse': {'GetCallerIdentityResult': result}})


def list_regions(c):
    if c.req.json().get('NextToken') == 'next':
        return c.render(json={'Regions': [{'RegionName': 'eu-central-1', 'RegionOptStatus': 'ENABLED'}]})
    c.render(
        json={'Regions': [{'RegionName': 'us-east-1', 'RegionOptStatus': 'ENABLED_BY_DEFAULT'}], 'NextToken': 'next'}
    )


def list_versions(c):
    if c.param('region') in broken:
        return c.render(json={'message': 'Service unavailable'}, status=503)
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
        'Content': {'CodeSha256': digest(b64_decode(body['Content']['ZipFile']))},
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


aws.routes.post('/us-east-1/sts/').to(cb=caller_identity)
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

# The messages of the log of the application, with their level only
app.log.format = lambda time, level, *lines: f'[{level}] {" ".join(map(str, lines))}\n'


def logged(*args):
    with app.log.capture('info') as messages:
        publish.run(*args)
    return [message.rstrip('\n') for message in messages]


with subtest('Dry run'):
    is_ok(
        logged('--python', '3.14', '--arch', config['architectures'][0]),
        [
            f'[info] [identity] 959435416781 {IDENTITY}',
            f'[info] [would publish] eu-central-1 {python}',
            f'[info] [would publish] us-east-1 {python}',
            f'[info] [would publish] eu-central-1 {layer}',
            f'[info] [keep] us-east-1 {layer} {arn}:2',
        ],
        'what it would do, with the latest version on the second page',
    )
    is_ok([r for r in requests if r[0] == 'POST' and 'lambda' in r[1]], [], 'nothing published')
    is_ok(callers[0], ('GetCallerIdentity', '2011-06-15', 'application/json'), 'GetCallerIdentity of STS, in JSON')
    ok(not os.path.exists(dist.child(f'{python}.json')), 'no ARNs')
    for method, path, authorization in requests:
        region, service = path.split('/')[1:3]
        like_ok(authorization, re.compile(rf'/{region}/{service}/aws4_request, '), f'{method} {path} signed')

with subtest('Apply'):
    requests.clear()
    is_ok(
        logged('--python', '3.14', '--arch', config['architectures'][0], '--apply'),
        [
            f'[info] [identity] 959435416781 {IDENTITY}',
            f'[info] [publish] eu-central-1 {python} arn:aws:lambda:eu-central-1:959435416781:layer:{python}:1',
            f'[info] [publish] us-east-1 {python} arn:aws:lambda:us-east-1:959435416781:layer:{python}:1',
            f'[info] [publish] eu-central-1 {layer} arn:aws:lambda:eu-central-1:959435416781:layer:{layer}:1',
            f'[info] [keep] us-east-1 {layer} {arn}:2',
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
    lines = logged('--python', '3.14', '--arch', config['architectures'][0], '--apply')
    is_ok([line.split()[1] for line in lines[1:]], ['[keep]'] * 4, 'nothing more to publish, already public')

with subtest('Excluded region'):
    config['excluded_regions'] = ['eu-central-1']
    lines = logged('--python', '3.14', '--arch', config['architectures'][0])
    is_ok([line.split()[2] for line in lines[1:]], ['us-east-1', 'us-east-1'], 'only the other region')
    config['excluded_regions'] = []

with subtest('Region that fails'):
    broken.add('eu-central-1')
    with app.log.capture('info') as messages:
        throws_ok(
            lambda: publish.run('--python', '3.14', '--arch', config['architectures'][0]),
            re.compile(rf'^Failed in 2 of the regions: eu-central-1 {python}, eu-central-1 {layer}'),
            'fails at the end',
        )
    lines = [message.rstrip('\n') for message in messages][1:]
    like_ok(
        lines[0],
        re.compile(rf'^\[error\] \[fail\] eu-central-1 {python} GET \S+: 503 : Service unavailable$'),
        'error of the region',
    )
    is_ok(
        lines[1],
        f'[info] [keep] us-east-1 {python} arn:aws:lambda:us-east-1:959435416781:layer:{python}:1',
        'others go on',
    )
    is_ok(len(lines), 4, 'every layer in every region')
    broken.clear()

with subtest('Concurrency'):
    with app.log.capture('info') as messages:
        publish.run('--python', '3.14', '--arch', config['architectures'][0], '-c', '1')
    is_ok(len(messages), 5, 'one region at a time')

with subtest('Index'):
    tmp = Pyjo.File.tempdir()
    arns = tmp.child('arns').make_path()
    account = 'arn:aws:lambda:{}:959435416781:layer:{}:{}'
    arns.child(f'{python}.json').spew(f'{{"us-east-1":"{account.format("us-east-1", python, 1)}"}}')
    arns.child(f'{layer}.json').spew(
        f'{{"us-east-1":"{account.format("us-east-1", layer, 2)}",'
        f'"eu-central-1":"{account.format("eu-central-1", layer, 2)}"}}'
    )
    arns.child('readme.txt').spew('not an ARN')
    index = LambdaLayers.Command.index.new()
    index.app = app
    output, notes, latest = tmp.child('layers.json'), tmp.child('notes.md'), tmp.child('latest.json')
    with app.log.capture('info') as messages:
        index.run('-o', output.to_str(), arns.to_str())
    is_ok(
        output.slurp().decode(),
        f'{{"{layer}":{{"eu-central-1":"{account.format("eu-central-1", layer, 2)}",'
        f'"us-east-1":"{account.format("us-east-1", layer, 2)}"}},'
        f'"{python}":{{"us-east-1":"{account.format("us-east-1", python, 1)}"}}}}\n',
        'index with its keys sorted',
    )
    is_ok([m.rstrip('\n') for m in messages], [f'[info] [write] {output}'], 'written')

    latest.spew('{}')
    index.run('-o', output.to_str(), '-l', latest.to_str(), '-n', notes.to_str(), arns.to_str())
    is_ok(
        notes.slurp().decode(),
        f'The layers with new versions:\n\n- `{layer}`: version 2\n- `{python}`: version 1\n',
        'notes of the first release',
    )

    notes.remove()
    output.copy_to(latest)
    with app.log.capture('info') as messages:
        index.run('-o', output.to_str(), '-l', latest.to_str(), '-n', notes.to_str(), arns.to_str())
    ok(not os.path.exists(notes), 'no release of the same layers')
    is_ok(messages[-1].rstrip('\n'), '[info] [same] the layers of the latest release', 'the same layers')

    arns.child(f'{layer}.json').spew(f'{{"us-east-1":"{account.format("us-east-1", layer, 3)}"}}')
    index.run('-o', output.to_str(), '-l', latest.to_str(), '-n', notes.to_str(), arns.to_str())
    is_ok(notes.slurp().decode(), f'The layers with new versions:\n\n- `{layer}`: version 3\n', 'a new version')
    throws_ok(lambda: index.run(), re.compile(r'^Usage: APPLICATION index'), 'usage without a directory')

with subtest('Errors'):
    throws_ok(
        lambda: LambdaLayers.aws(app.ua, 'GET', 'lambda', 'us-east-1', '/fail', endpoint='/{region}/{service}'),
        re.compile(r'^GET \S*/us-east-1/lambda/fail: 400 ValidationException: Bad request'),
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
