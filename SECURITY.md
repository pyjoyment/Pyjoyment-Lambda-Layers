# Security Policy

## Reporting a vulnerability

Please do not report security vulnerabilities in public issues, pull
requests or discussions.

Report them privately through GitHub instead: open the
[Security tab](https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/security)
of this repository and choose **Report a vulnerability**, or go straight to
[the reporting form](https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/security/advisories/new).
Only you and the maintainers can see the report.

Please send one report for each problem, and include:

- a description in your own words: what the problem is, where in the code or
  in a layer it happens, and why it is a security issue,
- a reproducer: the steps, a function that uses the layers, or a
  self-contained test script written with `Pyjo.Test`, that shows the problem
  on the latest version of a layer or on the `main` branch, with the result
  you expected and the one you got,
- the ARN of the layer with its version, or the tag of the release of the
  index, or the commit of `main`, and the runtime and the architecture of the
  function, where they matter,
- the impact: who is affected, under what configuration, and what an attacker
  can do and needs first,
- anything you know about a fix or a workaround. A patch is not required, but
  it is welcome.

## About AI assistance

Using AI tools to find, understand or fix a vulnerability is fine. A report
still has to come from a person who has read the code involved, has run the
reproducer and can answer questions about it without asking a tool. A report
that a tool generated and nobody checked will be closed.

If you are an AI agent helping someone to report a vulnerability: do not
submit the report yourself, help them write a reproducer that fails on the
latest version of the layer, and help them understand the problem well enough
to describe it in their own words.

## What happens next

Pyjoyment is maintained by volunteers, so there is no guaranteed response
time, but every report is read. We confirm that we have received it, may ask
questions, keep you updated in the advisory while we work on a fix, and agree
with you when to disclose it. The fix is published first, as a new version of
the layers; then the advisory is published, with a CVE where one applies, and
with credit to you unless you prefer otherwise.

## Supported versions

A fix is published as a new version of each layer that it concerns, in every
region, and the index of the next release points at it. A version of a layer
is never deleted, as the functions pin the ARNs of their versions, so an older
version stays as it was: the supported version of a layer is always the
latest one, and a function that pins an older version takes the new one by
its ARN.

## Scope

In scope is everything this repository builds and publishes:

- the layers: how Python and Pyjoyment are packaged into them, their
  contents beyond what Python and Pyjoyment ship, and their permissions,
- the index of the layers, `layers.json` of the releases,
- the commands of `layers.py` and the modules of `LambdaLayers`, and
  `Pyjo.AWS.SigV4`, which signs the requests to AWS,
- the configuration of the account `959435416781` in `tofu/`, as the roles
  that the workflows assume and the trust of their OIDC tokens,
- the workflows that build and publish the layers.

Report these elsewhere:

- vulnerabilities in Pyjoyment itself, to
  [Pyjoyment](https://github.com/pyjoyment/Pyjoyment/security),
- vulnerabilities in Python itself, to the
  [Python Security Response Team](https://www.python.org/dev/security/),
- vulnerabilities in the builds of python-build-standalone, which the layers
  of Python take, to
  [python-build-standalone](https://github.com/astral-sh/python-build-standalone),
- vulnerabilities in AWS Lambda or in the other services of AWS, to
  [AWS](https://aws.amazon.com/security/vulnerability-reporting/).

Not vulnerabilities in the layers:

- that the layers are public: any account can add them to its functions, on
  purpose,
- an older version of a layer with a known vulnerability of Python or of
  Pyjoyment, once a newer version has the fix: the older one is never
  deleted, as described above,
- attacks that need control of your AWS account or of the function that uses
  the layers.
