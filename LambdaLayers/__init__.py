"""
LambdaLayers - Layers of AWS Lambda of Python and Pyjoyment
===========================================================
::

    import LambdaLayers

    print(LambdaLayers.python_layer('3.14', 'arm64'))

:mod:`LambdaLayers` builds and publishes the layers of the versions of Python
and of the architectures of ``layers.toml``, for the commands of
``layers.py``, :mod:`LambdaLayers.Command.build`,
:mod:`LambdaLayers.Command.matrix` and :mod:`LambdaLayers.Command.publish`:
``python3_14-arm64``, Python for one architecture, and
``pyjoyment-python3_14``, Pyjoyment for both, which is the same file for both,
so the build of each architecture writes it, and the first architecture of
``layers.toml`` publishes it.
"""

import Pyjo.Exception
import Pyjo.File
import Pyjo.Iterator
import Pyjo.JSON
import Pyjo.Parameters
import Pyjo.Promise
import Pyjo.Transaction.HTTP
import Pyjo.UserAgent

from Pyjo.Util import b64_encode, sha256_bytes

import importlib
import importlib.metadata
import subprocess
import sys

from typing import Any, cast


# pyright takes the regular package Pyjo of Pyjoyment in .venv, which hides Pyjo.AWS of the checkout that extend_path
# finds at run time, so the module comes from importlib
SigV4: Any = importlib.import_module('Pyjo.AWS.SigV4')

# The URL of the APIs of AWS, which a test serves itself
ENDPOINT = 'https://{service}.{region}.amazonaws.com'

LAYERS = '/2018-10-31/layers'

type Config = dict[str, Any]


def python_layer(python: str, arch: str) -> str:
    """The name of the layer of Python of a version and an architecture."""
    return f'python{python.replace(".", "_")}-{arch}'


def pyjoyment_layer(python: str) -> str:
    """The name of the layer of Pyjoyment of a version of Python."""
    return f'pyjoyment-python{python.replace(".", "_")}'


def matrix(config: Config) -> dict[str, list[dict[str, str]]]:
    """The versions of Python and the architectures as the matrix of a workflow of GitHub Actions."""
    return {'include': [{'python': p, 'arch': a} for p in config['python'] for a in config['architectures']]}


# generate lambda-zip writes the ZIP files of the application of the current directory, so it runs in a directory of its
# own with pyproject.toml and uv.lock only, whose function.zip is left there
def build(home: Pyjo.File.object, python: str, arch: str, dist: Pyjo.File.object) -> list[Pyjo.File.object]:
    """Build the layers of Python and of Pyjoyment of a version and an architecture in a directory."""
    dist.make_path()
    with Pyjo.File.tempdir() as tmp:
        for name in ('pyproject.toml', 'uv.lock'):
            home.child(name).copy_to(tmp.child(name))
        command = [sys.executable, '-m', 'Pyjoyment', 'generate', 'lambda-zip', '--python', python, '--arch', arch]
        if (code := subprocess.run(command, cwd=tmp, stdout=subprocess.DEVNULL).returncode) != 0:
            raise Pyjo.Exception.new(f'Command "generate lambda-zip" failed with exit status {code}')
        files = {'python.zip': python_layer(python, arch), 'pyjoyment.zip': pyjoyment_layer(python)}
        paths = [dist.child(f'{layer}.zip') for layer in files.values()]
        for name, path in zip(files, paths, strict=True):
            tmp.child('dist', name).move_to(path)
    return paths


def publications(config: Config, python: str | None, arch: str | None) -> list[tuple[str, dict[str, Any]]]:
    """The names of the layers of a version and an architecture, all by default, and the parameters of
    PublishLayerVersion but the content."""
    result: list[tuple[str, dict[str, Any]]] = []
    for version in [python] if python else config['python']:
        for architecture in [arch] if arch else config['architectures']:
            params = {
                'Description': f'Python {version} of python-build-standalone',
                'CompatibleRuntimes': ['provided.al2023'],
                'CompatibleArchitectures': [architecture],
                'LicenseInfo': 'PSF-2.0',
            }
            result.append((python_layer(version, architecture), params))
            if architecture == config['architectures'][0]:
                runtime = f'python{version}'
                params = {
                    'Description': f'Pyjoyment {importlib.metadata.version("Pyjoyment")} for Python {version}',
                    'CompatibleRuntimes': ['provided.al2023', *([runtime] if runtime in config['runtimes'] else [])],
                    'CompatibleArchitectures': config['architectures'],
                    'LicenseInfo': 'Artistic-2.0',
                }
                result.append((pyjoyment_layer(version), params))
    return result


def aws(
    ua: Pyjo.UserAgent.object,
    method: str,
    service: str,
    region: str,
    path: str,
    body: dict[str, Any] | None = None,
    endpoint: str = ENDPOINT,
    allow: tuple[int, ...] = (),
    form: dict[str, str] | None = None,
) -> tuple[int, Any]:
    """A request to an API of AWS, signed, with a body of JSON or of a form, and the status and the JSON of its
    response."""
    tx = _signed(ua, method, service, region, endpoint.format(service=service, region=region) + path, body, form)
    return _result(ua.start(tx), allow)


def aws_p(
    ua: Pyjo.UserAgent.object,
    method: str,
    service: str,
    region: str,
    path: str,
    body: dict[str, Any] | None = None,
    endpoint: str = ENDPOINT,
    allow: tuple[int, ...] = (),
) -> Pyjo.Promise.object:
    """Same as aws, but non-blocking, and a promise of the status and the JSON of the response."""
    tx = _signed(ua, method, service, region, endpoint.format(service=service, region=region) + path, body, None)

    def result(tx: Pyjo.Transaction.HTTP.object) -> tuple[int, Any]:
        return _result(tx, allow)

    return ua.start_p(tx).then(result)


def identity(ua: Pyjo.UserAgent.object, endpoint: str = ENDPOINT) -> dict[str, str]:
    """The account and the ARN of the credentials, of GetCallerIdentity of STS, which every identity may call."""
    form = {'Action': 'GetCallerIdentity', 'Version': '2011-06-15'}
    _, data = aws(ua, 'POST', 'sts', 'us-east-1', '/', None, endpoint, form=form)
    return data['GetCallerIdentityResponse']['GetCallerIdentityResult']


def regions(ua: Pyjo.UserAgent.object, endpoint: str = ENDPOINT) -> list[str]:
    """The regions that the account has enabled."""
    names: list[str] = []
    body: dict[str, Any] = {'RegionOptStatusContains': ['ENABLED', 'ENABLED_BY_DEFAULT'], 'MaxResults': 50}
    while True:
        _, data = aws(ua, 'POST', 'account', 'us-east-1', '/listRegions', body, endpoint)
        names.extend(region['RegionName'] for region in data['Regions'])
        if not (token := data.get('NextToken')):
            return sorted(names)
        body['NextToken'] = token


async def latest(ua: Pyjo.UserAgent.object, region: str, name: str, endpoint: str = ENDPOINT) -> dict[str, Any] | None:
    """The latest version of a layer in a region, or None."""
    version, marker = 0, ''
    while True:
        query = Pyjo.Parameters.new({'MaxItems': 50, **({'Marker': marker} if marker else {})}).to_str()
        path = f'{LAYERS}/{name}/versions?{query}'
        code, data = await aws_p(ua, 'GET', 'lambda', region, path, None, endpoint, (404,))
        if code == 404:
            return None
        version = max([version, *(v['Version'] for v in data['LayerVersions'])])
        if not (marker := data.get('NextMarker')):
            break
    if not version:
        return None
    return (await aws_p(ua, 'GET', 'lambda', region, f'{LAYERS}/{name}/versions/{version}', None, endpoint))[1]


def publish(
    ua: Pyjo.UserAgent.object,
    regions: list[str],
    name: str,
    params: dict[str, Any],
    path: Pyjo.File.object,
    apply: bool = False,
    endpoint: str = ENDPOINT,
    concurrency: int = 4,
) -> Pyjo.Iterator.Pyjo_Iterator[tuple[str, str, str | None]]:
    """Publish a layer in the regions where the latest version differs, only with apply, and make its latest
    versions public: the region, what is done there, and the ARN of the latest version, or the error of a region
    that fails, which leaves the others to go on, in the order of the regions, as many of them at the same time as
    the concurrency."""
    content = cast(bytes, path.slurp())
    digest = b64_encode(sha256_bytes(content), '')

    async def region_p(region: str) -> tuple[str, str, str | None]:
        try:
            current = await latest(ua, region, name, endpoint)
            # The same content, with the same parameters, as the runtimes of a newer configuration
            if current is not None and current['Content']['CodeSha256'] == digest and _same(current, params):
                action = 'keep'
            elif apply:
                action = 'publish'
                body = {**params, 'Content': {'ZipFile': b64_encode(content, '')}}
                current = (await aws_p(ua, 'POST', 'lambda', region, f'{LAYERS}/{name}/versions', body, endpoint))[1]
            else:
                action, current = 'would publish', None
            # Public, also a version that an earlier run published and did not make public, which 409 says it is
            if apply and current is not None:
                policy = {'StatementId': 'public', 'Action': 'lambda:GetLayerVersion', 'Principal': '*'}
                resource = f'{LAYERS}/{name}/versions/{current["Version"]}/policy'
                await aws_p(ua, 'POST', 'lambda', region, resource, policy, endpoint, (409,))
        except Exception as e:
            return region, 'error', _message(e)
        return region, action, current['LayerVersionArn'] if current is not None else None

    # The values of the coroutines, which map passes on, where its type has the coroutines themselves
    results: Any = Pyjo.Iterator.new(regions).map(region_p, concurrency=concurrency)
    return results


def _same(current: dict[str, Any], params: dict[str, Any]) -> bool:
    """Whether a version of a layer has the parameters of a publication, with their lists in any order."""

    def value(v: Any) -> Any:
        return sorted(cast(list[str], v)) if isinstance(v, list) else v

    return all(value(current.get(k)) == value(v) for k, v in params.items())


def index(arns: Pyjo.File.object) -> dict[str, dict[str, str]]:
    """The index of the layers, {layer: {region: arn}}, of the files of the ARNs that publish writes in a directory,
    as python3_14-arm64.json."""
    return {
        file.basename('.json'): Pyjo.JSON.decode_json(cast(bytes, file.slurp()))
        for file in arns.list()
        if file.extname == 'json'
    }


def new_versions(index: dict[str, dict[str, str]], latest: dict[str, dict[str, str]]) -> dict[str, list[int]]:
    """The layers of an index that have versions which the latest index has not, as a new version or a new region,
    and these versions."""
    result: dict[str, list[int]] = {}
    for layer, arns in sorted(index.items()):
        known = latest.get(layer, {})
        if versions := sorted({int(arn.rsplit(':', 1)[1]) for region, arn in arns.items() if known.get(region) != arn}):
            result[layer] = versions
    return result


# A request built and signed in the event start of the user agent, where it has its URL, of the application of a test
# too, and its Host; only the transaction of the request, as several of them start at the same time
def _signed(
    ua: Pyjo.UserAgent.object,
    method: str,
    service: str,
    region: str,
    url: str,
    body: dict[str, Any] | None,
    form: dict[str, str] | None,
) -> Pyjo.Transaction.HTTP.object:
    if form is not None:
        tx = ua.build_tx(method, url, {'Accept': 'application/json'}, form=form)
    elif body is not None:
        tx = ua.build_tx(method, url, json=body)
    else:
        tx = ua.build_tx(method, url)
    signer: Any = SigV4.new(service=service, region=region)

    def sign(ua: Pyjo.UserAgent.object, started: Pyjo.Transaction.HTTP.object) -> None:
        if started is tx:
            ua.unsubscribe('start', sign)
            signer.sign(started.req)

    ua.on('start', sign)
    return tx


# The status and the JSON of a response, or the error of AWS or of the connection
def _result(tx: Pyjo.Transaction.HTTP.object, allow: tuple[int, ...]) -> tuple[int, Any]:
    req, res = tx.req, tx.res
    method, url = req.method, req.url.to_str()
    if (code := res.code) is None:
        raise Pyjo.Exception.new(f'{method} {url}: {tx.error["message"] if tx.error else "no response"}')
    data: Any = res.json() if res.body else None
    if code >= 300 and code not in allow:
        error = (res.headers.header('X-Amzn-ErrorType') or '').split(':')[0]
        fields = cast(dict[str, Any], data) if isinstance(data, dict) else {}
        message = fields.get('message') or fields.get('Message') or res.body.decode(errors='replace')
        raise Pyjo.Exception.new(f'{method} {url}: {code} {error}: {message}')
    return code, data


# The message of an error of a region, of Pyjo.Exception or of a promise rejected with a string
def _message(e: BaseException) -> str:
    return (e.message if isinstance(e, Pyjo.Exception.object) else str(e)).strip()
