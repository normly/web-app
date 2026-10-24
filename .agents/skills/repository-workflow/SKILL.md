---
name: repository-workflow
description: Use when setting up the normly development environment, choosing checks for a change, or preparing a contribution.
---

# Repository workflow

Use this guide to choose and run checks for a change. Read the root
[AGENTS.md](../../../AGENTS.md) for repository-wide constraints and
[CONTRIBUTING.md](../../../CONTRIBUTING.md) for contribution policy and the
human-facing setup and test commands. For project orientation, see the
[developer onboarding guide](../../../docs/guide/developer-onboarding.md).

## Run relevant checks

Identify the owning package with the [architecture skill](../architecture/SKILL.md),
then run the corresponding package test command from the repository root as
documented in `CONTRIBUTING.md`.

The full chat command runs end-to-end tests that start real API and accounts
processes and load the embedding model. CI excludes
`chat/tests/test_structural_end_to_end.py` to avoid the cold model download;
the test file is intended to run locally from the shared `.venv` when the
model is available. The CI workflow is authoritative for exact exclusions.

For frontend changes, follow the frontend test command in `CONTRIBUTING.md`.

For documentation changes, install the versions pinned in the `test-docs` job
of `.github/workflows/ci.yml` and run `zensical build`. For deployment
scripts, run the `shellcheck` and script tests listed in that workflow. The CI
workflow is the source of truth for the exact checks and any exclusions.

Run checks for all affected components; a passing test in one package does not
verify changes in another. Report any checks not run and why.
