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

The layers are published by the account `959435416781` in every commercial
region of AWS, as
`arn:aws:lambda:<region>:959435416781:layer:<name>:<version>`. A version of a
layer is never deleted.

`generate lambda-zip` of Pyjoyment builds the function that uses them.

## License

Artistic License 2.0 for Pyjoyment and this repository, and the license of the
Python Software Foundation for Python.
