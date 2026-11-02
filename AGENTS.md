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
The publication compares the `CodeSha256` of the latest version of a layer
with the SHA-256 of the file, and publishes only what differs, so a run is
started by hand or on a schedule, not on a push, and a run that failed is run
again.

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

Its pyright needs the environment of `uv sync`, `.venv`, which `tool.pyright`
of `pyproject.toml` names, as the code imports Pyjoyment; Trunk Check of CI
runs `uv sync` first. The modules of `Pyjo` of the repository are checked in
strict mode, and the tests are not checked: for them pyright takes the regular
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
