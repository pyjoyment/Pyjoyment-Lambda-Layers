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
import Pyjo.Transaction.HTTP
import Pyjo.UserAgent

import base64
import hashlib
import importlib
import importlib.metadata
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

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
def build(home: str, python: str, arch: str, dist: str) -> list[str]:
    """Build the layers of Python and of Pyjoyment of a version and an architecture in a directory."""
    os.makedirs(dist, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name in ('pyproject.toml', 'uv.lock'):
            shutil.copyfile(os.path.join(home, name), os.path.join(tmp, name))
        command = [sys.executable, '-m', 'Pyjoyment', 'generate', 'lambda-zip', '--python', python, '--arch', arch]
        if (code := subprocess.run(command, cwd=tmp, stdout=subprocess.DEVNULL).returncode) != 0:
            raise Pyjo.Exception.new(f'Command "generate lambda-zip" failed with exit status {code}')
        files = {'python.zip': python_layer(python, arch), 'pyjoyment.zip': pyjoyment_layer(python)}
        paths = [os.path.join(dist, f'{layer}.zip') for layer in files.values()]
        for (name, _), path in zip(files.items(), paths, strict=True):
            shutil.move(os.path.join(tmp, 'dist', name), path)
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
) -> tuple[int, Any]:
    """A request to an API of AWS, signed, and the status and the JSON of its response."""
    url = endpoint.format(service=service, region=region) + path
    tx = ua.build_tx(method, url, json=body) if body is not None else ua.build_tx(method, url)
    signer: Any = SigV4.new(service=service, region=region)

    def sign(ua: Pyjo.UserAgent.object, tx: Pyjo.Transaction.HTTP.object) -> None:
        signer.sign(tx.req)

    ua.once('start', sign)
    res = ua.start(tx).res
    if (code := res.code) is None:
        raise Pyjo.Exception.new(f'{method} {url}: {tx.error["message"] if tx.error else "no response"}')
    data: Any = res.json() if res.body else None
    if code >= 300 and code not in allow:
        error = (res.headers.header('X-Amzn-ErrorType') or '').split(':')[0]
        fields = cast(dict[str, Any], data) if isinstance(data, dict) else {}
        message = fields.get('message') or fields.get('Message') or res.body.decode(errors='replace')
        raise Pyjo.Exception.new(f'{method} {url}: {code} {error}: {message}')
    return code, data


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


def latest(ua: Pyjo.UserAgent.object, region: str, name: str, endpoint: str = ENDPOINT) -> dict[str, Any] | None:
    """The latest version of a layer in a region, or None."""
    version, marker = 0, ''
    while True:
        query = urllib.parse.urlencode({'MaxItems': 50, **({'Marker': marker} if marker else {})})
        code, data = aws(ua, 'GET', 'lambda', region, f'{LAYERS}/{name}/versions?{query}', None, endpoint, (404,))
        if code == 404:
            return None
        version = max([version, *(v['Version'] for v in data['LayerVersions'])])
        if not (marker := data.get('NextMarker')):
            break
    if not version:
        return None
    return aws(ua, 'GET', 'lambda', region, f'{LAYERS}/{name}/versions/{version}', None, endpoint)[1]


def publish(
    ua: Pyjo.UserAgent.object,
    regions: list[str],
    name: str,
    params: dict[str, Any],
    path: str,
    apply: bool = False,
    endpoint: str = ENDPOINT,
) -> list[tuple[str, str, str | None]]:
    """Publish a layer in the regions where the latest version differs, only with apply, and make its latest
    versions public, and the regions, what is done in each, and the ARNs of the latest versions."""
    with open(path, 'rb') as file:
        content = file.read()
    digest = base64.b64encode(hashlib.sha256(content).digest()).decode()
    result: list[tuple[str, str, str | None]] = []
    for region in regions:
        current = latest(ua, region, name, endpoint)
        if current is not None and current['Content']['CodeSha256'] == digest:
            action = 'keep'
        elif apply:
            action = 'publish'
            body = {**params, 'Content': {'ZipFile': base64.b64encode(content).decode()}}
            current = aws(ua, 'POST', 'lambda', region, f'{LAYERS}/{name}/versions', body, endpoint)[1]
        else:
            action, current = 'would publish', None
        # Public, also a version that an earlier run published and did not make public, which 409 says it is already
        if apply and current is not None:
            policy = {'StatementId': 'public', 'Action': 'lambda:GetLayerVersion', 'Principal': '*'}
            resource = f'{LAYERS}/{name}/versions/{current["Version"]}/policy'
            aws(ua, 'POST', 'lambda', region, resource, policy, endpoint, (409,))
        result.append((region, action, current['LayerVersionArn'] if current is not None else None))
    return result
