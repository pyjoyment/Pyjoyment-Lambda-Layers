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
``pyjoyment-0_3_0-python3_14``, Pyjoyment and Pyjo-AWS for both, which is
the same file for both, so the build of each architecture writes it, and the
first architecture of ``layers.toml`` publishes it. The index of the layers
has its alias too, ``pyjoyment-python3_14``, with the same ARNs.

The APIs of AWS are called with the clients of :mod:`Pyjo.AWS.Client`, of
:func:`clients`.
"""

import Pyjo.AWS.Client
import Pyjo.AWS.Config
import Pyjo.AWS.Credentials.Chain
import Pyjo.AWS.Error
import Pyjo.AWS.Protocol.Query
import Pyjo.AWS.Protocol.RestJSON
import Pyjo.DOM
import Pyjo.Exception
import Pyjo.File
import Pyjo.Iterator
import Pyjo.JSON
import Pyjo.UserAgent

from Pyjo.Util import b64_encode, sha256_bytes

import importlib.metadata
import re
import subprocess
import sys
import zipfile

from collections.abc import Callable
from typing import Any, cast


LAYERS = '/2018-10-31/layers'

# The distributions that the layer of Pyjoyment has besides Pyjoyment, which --layer-package of generate lambda-zip moves
# there with their metadata, and their packages
LAYERED = {'Pyjo-AWS': 'Pyjo/AWS'}

# The layers of Pyjoyment of a version of Pyjoyment, whose alias in the index is the name without it
VERSIONED = re.compile(r'^pyjoyment-[^-]+-(python[^-]+)$')

type Config = dict[str, Any]

type Clients = Callable[[str, str], Pyjo.AWS.Client.object]


def python_layer(python: str, arch: str) -> str:
    """The name of the layer of Python of a version and an architecture."""
    return f'python{python.replace(".", "_")}-{arch}'


def pyjoyment_layer(python: str, pyjoyment: str | None = None) -> str:
    """The name of the layer of Pyjoyment of a version of Python and of Pyjoyment, the installed one by default, with
    `_` for the characters that Lambda does not take in a name, as the dots."""
    version = pyjoyment or importlib.metadata.version('Pyjoyment')
    return f'pyjoyment-{re.sub(r"[^A-Za-z0-9]", "_", version)}-python{python.replace(".", "_")}'


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
        command.extend(f'--layer-package={d}' for d in LAYERED)
        if (code := subprocess.run(command, cwd=tmp, stdout=subprocess.DEVNULL).returncode) != 0:
            raise Pyjo.Exception.new(f'Command "generate lambda-zip" failed with exit status {code}')
        files = {'python.zip': python_layer(python, arch), 'pyjoyment.zip': pyjoyment_layer(python)}
        paths = [dist.child(f'{layer}.zip') for layer in files.values()]
        for name, path in zip(files, paths, strict=True):
            tmp.child('dist', name).move_to(path)
    if packages := missing(paths[1]):
        raise Pyjo.Exception.new(f'No {", ".join(packages)} in the layer of Pyjoyment {paths[1]}')
    return paths


def missing(path: Pyjo.File.object) -> list[str]:
    """The distributions of LAYERED that a ZIP file of the layer of Pyjoyment has not in its site-packages, as their
    package or their metadata, of the name that PEP 503 normalizes with `_`."""
    with zipfile.ZipFile(path) as file:
        names = file.namelist()

    def has(distribution: str, package: str) -> bool:
        metadata = re.compile(
            rf'/site-packages/{re.sub(r"[-_.]+", "_", distribution)}-[^/]+\.dist-info/METADATA$', re.I
        )
        return any(n.endswith(f'/site-packages/{package}/__init__.py') for n in names) and any(
            metadata.search(n) for n in names
        )

    return [d for d, p in LAYERED.items() if not has(d, p)]


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
                pyjoyment, aws = importlib.metadata.version('Pyjoyment'), importlib.metadata.version('Pyjo-AWS')
                params = {
                    'Description': f'Pyjoyment {pyjoyment} and Pyjo-AWS {aws} for Python {version}',
                    'CompatibleRuntimes': ['provided.al2023', *([runtime] if runtime in config['runtimes'] else [])],
                    'CompatibleArchitectures': config['architectures'],
                    'LicenseInfo': 'Artistic-2.0',
                }
                result.append((pyjoyment_layer(version, pyjoyment), params))
    return result


def clients(ua: Pyjo.UserAgent.object, endpoint: str | None = None) -> Clients:
    """The clients of the services in the regions, as aws('lambda', 'eu-central-1'), which share one configuration and
    one chain of credentials, so that those of a profile of SSO are read or refreshed once, and the user agent, with its
    timeouts. The endpoint is the one of the environment or of the profile, or the regional one, or one with the
    placeholders service and region, which a test serves itself."""
    config = Pyjo.AWS.Config.new()
    credentials = Pyjo.AWS.Credentials.Chain.new(config=config, ua=ua)

    def client(service: str, region: str) -> Pyjo.AWS.Client.object:
        url = endpoint.format(service=service, region=region) if endpoint else None
        return Pyjo.AWS.Client.new(
            service=service, region=region, endpoint=url, config=config, credentials=credentials, ua=ua
        )

    return client


def identity(aws: Clients) -> dict[str, str]:
    """The account and the ARN of the credentials, of GetCallerIdentity of STS, which every identity may call."""
    dom = aws('sts', 'us-east-1').call(Pyjo.AWS.Protocol.Query.new('GetCallerIdentity', version='2011-06-15'))
    return {name: _text(dom, f'GetCallerIdentityResult > {name}') for name in ('Account', 'Arn', 'UserId')}


def regions(aws: Clients) -> list[str]:
    """The regions that the account has enabled."""
    client = aws('account', 'us-east-1')
    names: list[str] = []
    body: dict[str, Any] = {'RegionOptStatusContains': ['ENABLED', 'ENABLED_BY_DEFAULT'], 'MaxResults': 50}
    while True:
        data = client.call(Pyjo.AWS.Protocol.RestJSON.new('POST', '/listRegions', body))
        names.extend(region['RegionName'] for region in data['Regions'])
        if not (token := data.get('NextToken')):
            return sorted(names)
        body['NextToken'] = token


async def latest(aws: Clients, region: str, name: str) -> dict[str, Any] | None:
    """The latest version of a layer in a region, or None."""
    client = aws('lambda', region)
    version, marker = 0, None
    while True:
        call = Pyjo.AWS.Protocol.RestJSON.new(
            'GET', f'{LAYERS}/{name}/versions', query={'MaxItems': 50, 'Marker': marker}
        )
        try:
            data = await client.call_p(call)
        except Pyjo.AWS.Error.object as e:
            if e.status == 404:
                return None
            raise
        version = max([version, *(v['Version'] for v in data['LayerVersions'])])
        if not (marker := data.get('NextMarker')):
            break
    if not version:
        return None
    return await client.call_p(Pyjo.AWS.Protocol.RestJSON.new('GET', f'{LAYERS}/{name}/versions/{version}'))


def publish(
    aws: Clients,
    regions: list[str],
    name: str,
    params: dict[str, Any],
    path: Pyjo.File.object,
    apply: bool = False,
    concurrency: int = 4,
) -> Pyjo.Iterator.Pyjo_Iterator[tuple[str, str, str | None]]:
    """Publish a layer in the regions where the latest version differs, only with apply, and make its latest
    versions public: the region, what is done there, and the ARN of the latest version, or the error of a region
    that fails, which leaves the others to go on, in the order of the regions, as many of them at the same time as
    the concurrency."""
    content = path.slurp()
    digest = b64_encode(sha256_bytes(content), '')

    async def region_p(region: str) -> tuple[str, str, str | None]:
        try:
            client = aws('lambda', region)
            current = await latest(aws, region, name)
            # The same content, with the same parameters, as the runtimes of a newer configuration
            if current is not None and current['Content']['CodeSha256'] == digest and _same(current, params):
                action = 'keep'
            elif apply:
                action = 'publish'
                body = {**params, 'Content': {'ZipFile': b64_encode(content, '')}}
                current = await client.call_p(Pyjo.AWS.Protocol.RestJSON.new('POST', f'{LAYERS}/{name}/versions', body))
            else:
                action, current = 'would publish', None
            # Public, also a version that an earlier run published and did not make public, which 409 says it is
            if apply and current is not None:
                policy = {'StatementId': 'public', 'Action': 'lambda:GetLayerVersion', 'Principal': '*'}
                resource = f'{LAYERS}/{name}/versions/{current["Version"]}/policy'
                try:
                    await client.call_p(Pyjo.AWS.Protocol.RestJSON.new('POST', resource, policy))
                except Pyjo.AWS.Error.object as e:
                    if e.status != 409:
                        raise
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
        file.basename('.json'): Pyjo.JSON.decode_json(file.slurp()) for file in arns.list() if file.extname == 'json'
    }


def aliases(index: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """The index with the alias of each layer of Pyjoyment of a version of Pyjoyment, as pyjoyment-python3_14 of
    pyjoyment-0_3_0-python3_14, with the same ARNs, which no layer of AWS has as its name."""
    return {**index, **{f'pyjoyment-{m[1]}': arns for layer, arns in index.items() if (m := VERSIONED.match(layer))}}


def new_versions(index: dict[str, dict[str, str]], latest: dict[str, dict[str, str]]) -> dict[str, list[int]]:
    """The layers of an index that have versions which the latest index has not, as a new version or a new region,
    and these versions."""
    result: dict[str, list[int]] = {}
    for layer, arns in sorted(index.items()):
        known = latest.get(layer, {})
        if versions := sorted({int(arn.rsplit(':', 1)[1]) for region, arn in arns.items() if known.get(region) != arn}):
            result[layer] = versions
    return result


# The text of an element of the XML of a response, which AWS always has
def _text(dom: Pyjo.DOM.object, selector: str) -> str:
    if (element := dom.at(selector)) is None:
        raise Pyjo.Exception.new(f'No {selector} in the response of AWS')
    return element.text


# The message of an error of a region, of Pyjo.AWS.Error, of Pyjo.Exception or of a promise rejected with a string
def _message(e: BaseException) -> str:
    return (e.message if isinstance(e, Pyjo.Exception.object) else str(e)).strip()
