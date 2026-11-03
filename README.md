# Pyjoyment Lambda Layers

Public layers of AWS Lambda with Python and with
[Pyjoyment](https://github.com/pyjoyment/Pyjoyment), for the event functions
of Pyjoyment, so that a function takes them by their ARNs instead of carrying
them in its ZIP file.

- `python3_14-arm64`, `python3_14t-x86_64`, ...: Python, for the custom
  runtime `provided.al2023`, of one version and one architecture, the
  free-threaded build too.
- `pyjoyment-python3_14`, `pyjoyment-python3_14t`, ...: Pyjoyment, for both
  architectures, with the layer of Python on `provided.al2023` or on the
  runtime of Python of AWS Lambda of the same version.

The layers are published by the account `959435416781` in the commercial
regions of AWS, as
`arn:aws:lambda:<region>:959435416781:layer:<name>:<version>`. A version of a
layer is never deleted.

`generate lambda-zip` of Pyjoyment builds the function that uses them.

## The ARNs

A function takes a layer by the ARN of a version, which the index of the
layers gives, `layers.json` of each release, as `{layer: {region: arn}}`.
The latest one is always at the same URL, which a one-liner of Pyjoyment
reads with a JSON Pointer:

```sh
uv run --with Pyjoyment python -m Pyjo \
  'g("https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/releases/latest/download/layers.json").json("/pyjoyment-python3_14/eu-central-1")'
```

`curl -sL` of the same URL with `jq -r '.["pyjoyment-python3_14"]["eu-central-1"]'`
gives the same without Python.

A release, as `2026.11.03`, keeps its index, so that a deployment can stay
on the layers of a day.

## License

Artistic License 2.0 for Pyjoyment and this repository, and the license of the
Python Software Foundation for Python.
