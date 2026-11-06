[![Home](https://img.shields.io/badge/%F0%9F%8F%A0-Pyjoyment-02a7a0)](https://pyjoyment.dev/)
[![GitHub](https://img.shields.io/github/stars/pyjoyment/Pyjoyment-Lambda-Layers?style=flat&label=GitHub%20%E2%AD%90&logo=github)](https://github.com/pyjoyment/Pyjoyment-Lambda-Layers)
[![License](https://img.shields.io/github/license/pyjoyment/Pyjoyment-Lambda-Layers.svg)](https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/blob/main/LICENSE)
[![Tests](https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/actions/workflows/tests.yaml/badge.svg?branch=main)](https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/actions/workflows/tests.yaml)
[![Trunk Check](https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/actions/workflows/trunk-check.yaml/badge.svg?branch=main)](https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/actions/workflows/trunk-check.yaml)
[![Publish](https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/actions/workflows/publish.yaml/badge.svg?branch=main)](https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/actions/workflows/publish.yaml)

# Pyjoyment Lambda Layers

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/pyjoyment/Pyjoyment/main/Pyjoyment/resources/public/pyjo/logo-white-4x.png">
    <img src="https://raw.githubusercontent.com/pyjoyment/Pyjoyment/main/Pyjoyment/resources/public/pyjo/logo-black-4x.png" alt="Pyjoyment" width="322">
  </picture>
</p>

Public layers of AWS Lambda with Python and with
[Pyjoyment](https://pyjoyment.dev/), for the event functions
of Pyjoyment, so that a function takes them by their ARNs instead of carrying
them in its ZIP file.

- `python3_14-arm64`, `python3_14t-x86_64`, ...: Python, for the custom
  runtime `provided.al2023`, of one version and one architecture, the
  free-threaded build too.
- `pyjoyment-0_3_0-python3_14`, `pyjoyment-0_3_0-python3_14t`, ...: a
  version of Pyjoyment and [Pyjo-AWS](https://github.com/pyjoyment/Pyjo-AWS),
  for both architectures, with the layer of Python on `provided.al2023` or on
  the runtime of Python of AWS Lambda of the same version.

The layers are published by the account `959435416781` in the commercial
regions of AWS, as
`arn:aws:lambda:<region>:959435416781:layer:<name>:<version>`. A version of a
layer is never deleted.

`generate lambda-zip --function-only` of Pyjoyment builds the function that
uses them, `function.zip` alone, and names the version of Pyjoyment of the
layer that it needs:

```sh
./myapp.py generate lambda-zip --python 3.14 --arch arm64 --function-only
```

## The ARNs

A function takes a layer by the ARN of a version, which the index of the
layers gives, `layers.json` of each release, as `{layer: {region: arn}}`. It
has the layers of the latest Pyjoyment, and for each of them an alias without
the version of Pyjoyment, as `pyjoyment-python3_14`, with the same ARNs. The
latest one is always at the same URL, which a one-liner of Pyjoyment reads
with a JSON Pointer:

```sh
uv run --with Pyjoyment python -m Pyjo \
  'g("https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/releases/latest/download/layers.json").json("/pyjoyment-python3_14/eu-central-1")'
```

`curl -sL` of the same URL with `jq -r '.["pyjoyment-python3_14"]["eu-central-1"]'`
gives the same without Python.

A release, as `0.3.0+2026.11.05`, of the version of Pyjoyment and the date,
keeps its index, so that a deployment can stay on the layers of a day. The
latest release of a version of Pyjoyment, whose index has its layers, is the
first one whose tag has its prefix:

```sh
gh release list --repo pyjoyment/Pyjoyment-Lambda-Layers --limit 1000 \
  --json tagName --jq '[.[].tagName | select(startswith("0.3.0+"))][0]'
```

## License

Artistic License 2.0 for Pyjoyment, Pyjo-AWS and this repository, and the license of the
Python Software Foundation for Python.
