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
- `pyjoyment-python<major>_<minor>[t]`: `pyjoyment.zip`, Pyjoyment in
  `python/lib/python3.X/site-packages`, whose path and bytecode are of one
  version of Python but of no architecture, for `provided.al2023` and the
  runtime of Python of AWS Lambda of the same version.

A version of a layer is never deleted, as a function pins the ARN of a
version, and a deleted one cannot be added to a function again.

The command line of Pyjoyment builds the files, `generate lambda-zip`, whose
files of the same input are the same. The build of Python is the one that the
uv of `mise.toml` installs, so a bump of uv gives a new layer of Python with
the same Pyjoyment, and the Pyjoyment of the layers is the one of `uv.lock`.

`layers.py` is an application of `Pyjoyment.Lite`, whose configuration is
`layers.toml` of `TOMLConfig`, with the versions of Python, the architectures
and the runtimes of Python of Lambda, and whose commands are those of the
namespace `LambdaLayers.Command`, with their options of `getopt` and their
usage of their docstrings, as the commands of Pyjoyment: `build` builds the
layers in `dist`, all of them or one version and architecture with `--python`
and `--arch`, `matrix` gives them to the workflows as their matrix, one job for
each version and architecture, and `publish` publishes them. The code that
they share is `LambdaLayers`.

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
the SHA-256 of its file. It only shows what it would publish, unless
`--apply` is given, which only the workflow of the publication gives, so that
a run anywhere else changes nothing. With `--apply`, it publishes the files
that differ and makes the latest versions public, also a version that an
earlier run published and did not make public, as `AddLayerVersionPermission`
answers 409 for a version that is public already, and writes the ARNs of the
latest versions in `dist`. A run is started by hand or on a schedule, not on a
push, and a run that failed is run again.

The requests are signed with the credentials of the environment, which
`Pyjo.AWS.SigV4` reads, not with a profile of AWS, so a run on a machine with
a profile of SSO exports its credentials first:

```sh
eval "$(aws configure export-credentials --profile <profile> --format env)"
```

`t/layers_commands.py` runs the commands against an application of Pyjoyment
that serves the APIs of AWS that they use, by the `endpoint` of `publish`.

## The Account

`tofu/` is the configuration of the account `959435416781`: the OIDC provider
of GitHub, the role `Pyjoyment-Lambda-Layers-publishing`, which only the jobs
of the environment `publishing` of this repository assume, the regions that
need an opt-in, and the bucket of its own state. It is applied by hand, with
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

## Signature Version 4

`Pyjo.AWS.SigV4` signs the requests of `Pyjo.UserAgent` to the APIs of AWS,
without an SDK. It is a module of the namespace `Pyjo` of Pyjoyment, which
`extend_path` keeps open: the directory `Pyjo` of the repository has no
`__init__.py`, only `Pyjo/AWS` has one, so that it can move to a distribution
of its own without a change of its imports.

The event `start` of the user agent signs a request, as it comes for each
transaction, a redirect too, once the request is complete. The request has no
`Host` and no `Content-Length` then, which `fix_headers` of the request adds
when it is written, so `sign` sets `Host` itself, and `Content-Length` is not
signed, which AWS does not require. The headers that a proxy or the user agent
may change after the signature, as `User-Agent` and `Expect`, are not signed,
as the SDKs of AWS leave them.

The path of the canonical request is the one that HTTP sends, already
percent-encoded, which `double_encode` encodes again, as every service but S3
wants. `t/aws-signing-test-suite` has the cases of the test suite of
aws-c-auth, kept as they are, which `biome.jsonc` leaves out. The suite sends a
path with a space or UTF-8 as it is, which HTTP cannot, so the test skips
those cases, and the one of a session token that is not signed, of AWS IoT,
which `Pyjo.AWS.SigV4` does not have.

## Tests

The tests are scripts of `Pyjo.Test` in `t`, which `Pyjo.Prove` runs, on the
reactor of asyncio and on the one of poll, in the development mode of Python,
as the workflow Tests does:

```sh
PYTHONDEVMODE=1 mise exec -- uv run python -m Pyjo.Prove -l --capture-stderr -r t
PYJO_REACTOR=Pyjo.Reactor.Poll PYTHONDEVMODE=1 mise exec -- uv run python -m Pyjo.Prove -l --capture-stderr -r t
```

`-l` puts the checkout in `PYTHONPATH`, where `extend_path` of the `Pyjo` of
Pyjoyment finds the modules of `Pyjo` of the repository.

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
`package.json`. Renovate cannot run `biome migrate`, so the workflow Biome
Migrate runs it with `npx --yes @biomejs/biome@<version>` of that version,
migrates `biome.jsonc` on the branch of Renovate and commits it with the token
of the workflow, as the author that `gitIgnoredAuthors` of `.renovaterc.json`
names, so that Renovate keeps updating the branch, and starts the checks of
the commit with `workflow_dispatch`; anywhere else, a `biome.jsonc` that this
Biome would migrate fails the check. The definition of Biome in
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
runs `uv sync` first. `LambdaLayers` and the modules of `Pyjo` of the repository are
checked in strict mode, and the tests are not checked: for them pyright takes the regular
package `Pyjo` of Pyjoyment, which hides the modules of the checkout.

The workflows that start the checks of a commit of the token of a workflow, as
Automated trunk upgrade and Biome Migrate, start every check that the ruleset
of `main` requires: a new required check is added to them too.

## Security

Never read, display, reference, or include the contents of the following
files:

- `.env`, `.env.*`, `.envrc`
- `.pypirc`
- `*.jks`, `*.keystore`, `*.p12`, `*.pfx`, `*.pem`, `*.key`

The rules of `permissions.deny` of `.claude/settings.json` enforce it for
Claude Code, as in Pyjoyment.

The publication runs with the credentials of the OIDC of GitHub, of a role of
the account that only the environment `publishing` of this repository assumes,
never with keys of a user.

## Commits and Pull Requests

As in Pyjoyment: short subjects in the style of the history, mechanical and
functional changes in separate commits, and a pull request with a validation
checklist, checked only once verified.
