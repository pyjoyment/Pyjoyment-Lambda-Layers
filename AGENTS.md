# Agent Guide: Pyjoyment-Lambda-Layers

## Overview

The repository builds the public layers of AWS Lambda with Python and with
Pyjoyment, and publishes them from the account `959435416781` in every
commercial region. It is not a distribution: it installs nothing of its own,
and its code is the build, the publication and the infrastructure of the
account. The conventions are those of Pyjoyment: read its `AGENTS.md` in the
checkout next to this one, `../Pyjoyment/AGENTS.md`.

## The Layers

The names are predictable, as a user writes them in an ARN, and have only
`[A-Za-z0-9_-]`, as Lambda requires:

- `python<major>_<minor>[t]-<arch>`: `python.zip` of `generate lambda-zip`,
  Python of python-build-standalone for one architecture, for
  `provided.al2023`.
- `pyjoyment-<major>_<minor>_<patch>-python<major>_<minor>[t]`:
  `pyjoyment.zip`, Pyjoyment and Pyjo-AWS in
  `python/lib/python3.X/site-packages`, whose path and bytecode are of one
  version of Python but of no architecture, for `provided.al2023` and the
  runtime of Python of AWS Lambda of the same version.

A version of a layer is never deleted, as a function pins the ARN of a
version, and a deleted one cannot be added to a function again.

The layer of Pyjoyment has the version of Pyjoyment in its name, with `_` for
the characters that Lambda does not take, as the dots, so that a function of
`generate lambda-zip --function-only`, which tells the version of Pyjoyment
that it was built with, takes the layer of that version by its name: the
number of a version of a layer tells nothing, and the description of a layer
is not in its ARN. The version of Pyjo-AWS is in the description only, so its
bump is a new version of the same layer. A release of Pyjoyment gives new
layers, and those of the previous version get no new versions after it, not
even of a fix of the build.

The command line of Pyjoyment builds the files, `generate lambda-zip`, whose
files of the same input are the same. The build of Python is the one that the
uv of `mise.toml` installs, so a bump of uv gives a new layer of Python with
the same Pyjoyment, and the Pyjoyment and the Pyjo-AWS of the layers are those
of `uv.lock`.

Pyjo-AWS is in the layer of Pyjoyment, so that a function on the public layers
calls AWS without a dependency of its own, as a function of
`generate lambda-zip --function-only --layer-package Pyjo-AWS` leaves it out
of its dependencies, which the layer is to have. It is a dependency of the
project, not of the group `dev`, which `uv export --no-dev` of
`generate lambda-zip` would leave out, and the commands use the same
Pyjo-AWS. Without the extra `cryptography`, whose wheels are of an
architecture, where the layer is of none: `Pyjo.AWS.ECDSA` signs with Python
then. The layer of Pyjoyment of `generate lambda-zip` has the files of the
`RECORD` of Pyjoyment only, so `build` passes `--layer-package` for each
distribution of `LAYERED` of `LambdaLayers`, which moves it to the layer with
its `dist-info`, and fails when the layer has not its package or its
`dist-info`, as the dry run of a pull request of Renovate that bumps
Pyjoyment then shows.

`layers.py` is an application of `Pyjoyment.Lite`, whose configuration is
`layers.toml` of `TOMLConfig`, with the versions of Python, the architectures
and the runtimes of Python of Lambda, and whose commands are those of the
namespace `LambdaLayers.Command`, with their options of `getopt` and their
usage of their docstrings, as the commands of Pyjoyment: `build` builds the
layers in `dist`, all of them or one version and architecture with `--python`
and `--arch`, `matrix` gives them to the workflows as their matrix, one job for
each version and architecture, `publish` publishes them, and `index` merges
their ARNs into the index of a release. The code that they share is
`LambdaLayers`.

```sh
mise exec -- uv run python layers.py build --python 3.14 --arch arm64
mise exec -- uv run python layers.py publish --python 3.14 --arch arm64
```

`generate lambda-zip` writes the ZIP files of the application of the current
directory, so `build` runs it in a temporary directory with `pyproject.toml`
and `uv.lock` only, as the default application of Pyjoyment, and leaves its
`function.zip` there. The layer of Pyjoyment has no code of an architecture,
so the builds of both architectures write the same file, and only the first
architecture of `layers.toml` publishes it, so that two jobs do not publish it
at the same time.

`publish` takes the regions that the account has enabled from
`account:ListRegions`, and compares the `CodeSha256` of the latest version of
each layer in each of them, the highest version of `ListLayerVersions`, with
the SHA-256 of its file, and its parameters, as the description and the
compatible runtimes, with those of the publication, with their lists in any
order, so that a runtime of Python that `layers.toml` adds publishes the same
file again. It only shows what it would publish, unless `--apply` is given,
which only the workflow of the publication gives, so that a run anywhere else
changes nothing. With `--apply`, it publishes the files that differ and makes
the latest versions public, also a version that an earlier run published and
did not make public, as `AddLayerVersionPermission` answers 409 for a version
that is public already, and writes the ARNs of the latest versions in `dist`.
A run is started by hand or on a schedule, not on a push, and a run that
failed is run again.

The regions of a layer are done at the same time, four of them by default, as
`--concurrency` says, with the calls of `Pyjo.AWS.Client` that give promises,
`call_p`, in the coroutine of a region, which `Pyjo.Iterator.map` runs ahead, so that
the regions come out in their order as they are done. A layer of Python of 17
MB to more than thirty regions one after another takes minutes, and a region
that answers slowly holds back only one of the four.
A request has 120 seconds at most and 60 without data, so a region that hangs
or trickles fails after a minute or two, as `[fail]`, and the job of the
workflow has 20 minutes, where the user agent has no limit by default.

The commands report what they do in the log of the application, on the
standard error, which `Pyjo.Log` flushes at each message, and not with
`_loud` of `Pyjoyment.Command`, a private method of the framework; the
standard output is for the result of a command, as the JSON of `matrix`. The
workflows set `PYJO_LOG_FORMAT=plain`, without the time and the process, which
the log of GitHub Actions has itself.

The workflow Publish runs `build` and `publish` in a job for each version of
Python and architecture of the matrix. A pull request, and a dispatch on
`main` with the input `mode` set to `dry-run`, run them without `--apply`,
with the role that only reads, so that they show what they would publish,
without the index; the schedule, weekly, and a dispatch on `main` run them with
`--apply`, in the environment `publishing`, which takes `main` only and waits
for no approval, as the code on `main` comes through pull requests, and the
last job merges the ARNs of the jobs into `layers.json`,
`{layer: {region: arn}}`, with its keys sorted, with the command `index`, which
writes the notes of a release, with the new versions, only when the index
differs from the one of the latest release. A pull request of a fork has no
role to assume, so it has no dry run.

The index has the layers of the run only, not those of the releases before
it, so that its size is the same for every version of Pyjoyment, and the
alias of each layer of Pyjoyment, its name without the version of Pyjoyment,
as `pyjoyment-python3_14` of `pyjoyment-0_3_0-python3_14`, with the same
ARNs, for whoever takes the latest Pyjoyment, as the examples of Pyjoyment. No
layer of AWS is published under the name of an alias. The notes list the new
versions without the aliases, which would list each layer of Pyjoyment twice.

The index is released when `index` writes the notes, so when a layer has a
new version or a new region, and a weekly run that keeps everything releases
nothing; `gh` downloads the index of the latest release and makes the
release. The tag is the version of Pyjoyment of the layers and the date in
UTC, as `0.3.0+2026.11.05`, without a `v`, as the tags of Pyjoyment, with
`.2` and on for another release of the same day, on the commit that the
layers were built of, and the notes list the layers with new versions. The
date is the build metadata of semantic versioning, which its precedence leaves
out, so the tag is not a pre-release of `0.3.0`, as `0.3.0-2026.11.05` would
be. The releases of a version of Pyjoyment are those of the tags of its
prefix, `0.3.0+`, and the latest of them has the layers of that version: GitHub
has no latest release of a prefix, so it is the first of `gh release list`
whose tag has it.

The index of the latest release is at
`releases/latest/download/layers.json`, so its format,
`{layer: {region: arn}}`, which `jq` and `yq` read without a library, and the
alias are a contract: a change of them breaks whoever reads it. `gh release
create` marks the release as the latest one with `--latest`, which GitHub
otherwise takes from the date and the highest semantic version, as
`2026.11.05` of the tags of the date alone. A failed job of the publication
releases nothing, as the index would miss its layers; the next run, which
keeps what is published already, releases them all.

The APIs of AWS are called with `Pyjo.AWS.Client` of Pyjo-AWS, with the
credentials that the AWS CLI finds, of the environment first, which
`aws-actions/configure-aws-credentials` of the workflows sets, and of a
profile, so a run on a machine takes a profile of SSO or of `aws login`
directly:

```sh
AWS_PROFILE=<profile> mise exec -- uv run python layers.py publish --python 3.14 --arch arm64
```

The clients of `clients` of `LambdaLayers`, one for a service in a region,
share one configuration and one chain of credentials, so that those of a
profile are read or refreshed once, and the user agent of the application, with
the timeouts of `publish`. The errors that `publish` allows, 404 of a layer
that a region has not and 409 of a version that is public already, are a
`Pyjo.AWS.Error` with its `status`.

`t/layers_commands.py` runs the commands against an application of Pyjoyment
that serves the APIs of AWS that they use, by the `endpoint` of `publish`, with
the placeholders `service` and `region`, which an endpoint of
`AWS_ENDPOINT_URL_<SERVICE>` has not, and without the shared files of AWS of
the machine.

## The Account

`tofu/` is the configuration of the account `959435416781`: the OIDC provider
of GitHub, the role `Pyjoyment-Lambda-Layers-publishing`, which only the jobs
of the environment `publishing` of this repository assume, the role
`Pyjoyment-Lambda-Layers-dry-run`, which only reads, for the jobs of its pull
requests and of a dispatch on `main` in the mode `dry-run`, the regions that need an opt-in, and the bucket of its own state. It is applied by hand, with
the credentials of `AWS_PROFILE`, never by CI, and `allowed_account_ids` of
the provider stops a profile of another account before it changes anything:

```sh
cd tofu
mise exec -- tofu init
mise exec -- tofu plan -out=tfplan
mise exec -- tofu apply tfplan
```

The repository has the immutable subject of the OIDC tokens of GitHub, with
the IDs of its owner and of itself,
`repo:pyjoyment@351424207/Pyjoyment-Lambda-Layers@1443233156`, so the trust
of the role names the IDs, not only the names, and a repository of the same
name made anew does not get the role.

A document of a policy takes no attribute of another resource, as the ARN of
the OIDC provider in the trust of the role: such a value is unknown until the
apply, and the plan shows the document as `(known after apply)` instead of its
statements. The document builds the ARN from the account itself, and
`depends_on` of the resource that uses it gives the order.

The layers are published in every region that the account has enabled, which
the publication takes from `account:ListRegions`, not from a list of its own.
The configuration enables every region that needs an opt-in, as `aws_regions`
lists them, so a new region of AWS is enabled by the next apply, and never
disables one, which `prevent_destroy` keeps from happening, as the layers
published there would go with it.

The state is in the bucket `pyjoyment-tofu-state-959435416781` of
`us-east-1`, with its versions and the lock file of the backend `s3`
(`use_lockfile`), and the bucket is a resource of the same configuration. A new
account starts with a local state: `tofu/backend_override.tf`, which
`.gitignore` ignores, with `terraform { backend "local" {} }`, `tofu init` and
the apply, which creates the bucket, and then, without the file,
`tofu init -migrate-state`.

## Tests

The tests are scripts of `Pyjo.Test` in `t`, which `Pyjo.Prove` runs, on the
reactor of asyncio and on the one of poll, in the development mode of Python,
as the workflow Tests does:

```sh
PYTHONDEVMODE=1 mise exec -- uv run python -m Pyjo.Prove -l --capture-stderr -r t
PYJO_REACTOR=Pyjo.Reactor.Poll PYTHONDEVMODE=1 mise exec -- uv run python -m Pyjo.Prove -l --capture-stderr -r t
```

`-l` puts the checkout in `PYTHONPATH`, where the tests find `LambdaLayers`.

## Development

```sh
mise install
mise exec -- uv sync
```

Trunk checks the files with the linters of Pyjoyment, from
`.trunk/trunk.yaml`:

```sh
trunk check --all --no-fix
```

actionlint is the one of the maintained fork kjanat/actionlint, as in
Pyjoyment: `downloads` in `.trunk/trunk.yaml` replaces the URLs of the plugin
with those of the fork, whose files have the same names.

Biome formats and lints JSON, Markdown and YAML, with `biome.jsonc`, and
yamllint checks what Biome does not, as the duplicated keys. The version of
Biome is the pinned one of `.trunk/trunk.yaml`, where `!` keeps it from
`trunk upgrade`, and which Renovate bumps: the repository has no
`package.json`. Renovate cannot run `biome migrate` nor `biome format`, so the
workflow Biome Migrate runs them with `npx --yes @biomejs/biome@<version>` of
that version, migrates `biome.jsonc` and formats the files that the new version
formats otherwise, which Trunk Check would fail on, on the branch of Renovate,
and commits them with the token of the workflow, as the author that
`gitIgnoredAuthors` of `.renovaterc.json` names, so that Renovate keeps
updating the branch, and starts the checks of the commit with
`workflow_dispatch`; anywhere else, a file that this Biome would migrate or
format fails the check. The token cannot change a workflow, so a file of
`.github/workflows` that the new Biome formats otherwise fails the push of the
commit, and is formatted by hand. The definition of Biome in
`.trunk/trunk.yaml` is the one of Pyjoyment, which explains why it is not the
one of the plugin of Trunk.

tflint checks `tofu/` with the rules of its plugins `terraform` and `aws`, from
`.tflint.hcl` in the root of the repository, where the extensions of the
editors find it. Trunk runs tflint in the directory of the files, where tflint
looks for its configuration, so the definition of tflint in
`.trunk/trunk.yaml` names the file in `TFLINT_CONFIG_FILE`. `tflint --init`
downloads the plugins from the releases of GitHub, whose API limits the
requests without a token, so Trunk Check of CI has `GITHUB_TOKEN`, and a local
run that fails with the limit of the API takes the one of `gh`:

```sh
GITHUB_TOKEN=$(gh auth token) trunk check --all --no-fix
```

Its pyright needs the environment of `uv sync`, `.venv`, which `tool.pyright`
of `pyproject.toml` names, as the code imports Pyjoyment; Trunk Check of CI
runs `uv sync` first. `LambdaLayers` is checked in strict mode, and the tests
are not checked.

The workflows that start the checks of a commit of the token of a workflow, as
Automated trunk upgrade and Biome Migrate, start every check that the ruleset
of `main` requires: a new required check is added to them too.

## Security

Never read, display, reference, or include the contents of the following
files:

- `.env`, `.env.*`, `.envrc`
- `.pypirc`
- `*.jks`, `*.keystore`, `*.p12`, `*.pfx`, `*.pem`, `*.key`

The same list is git-ignored in `.gitignore`, and the rules of
`permissions.deny` of `.claude/settings.json` enforce it for Claude Code, as
in Pyjoyment: change all three together.

The publication runs with the credentials of the OIDC of GitHub, of a role of
the account that only the environment `publishing` of this repository assumes,
never with keys of a user.

## Commits and Pull Requests

As in Pyjoyment: short subjects in the style of the history, mechanical and
functional changes in separate commits, and a pull request with a validation
checklist, checked only once verified.
