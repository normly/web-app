# Releasing

A release is one git tag that produces one version of all five images
([ADR-023](../adr/README.md#adr-023-image-pipeline-ghcr-keyless-signing-one-version-lock-file)).
Images are built, signed and published by the `Images` workflow
(`.github/workflows/images.yml`); nobody builds release images by hand.

## What gets published

| Trigger | Tags on every image |
|---|---|
| merge to `main` | `edge`, `sha-<short commit>` |
| tag `vX.Y.Z` | `X.Y.Z`, `X.Y`, `latest`, `sha-<short commit>` |

Images: `ghcr.io/normly/web-app/{api,chat,accounts,pipeline,frontend}`.
`latest` always means the newest release, never `edge`. Only `vX.Y.Z`
tags publish (no pre-release tags yet), and manual runs are accepted only
from `main` or a release tag.

`main` changes only through releases and hotfixes (ADR-028), so `edge`
tracks production. Day-to-day work is merged into `develop`, which builds
no images.

## Cutting a release

1. Set the same version in all five places and commit it on a
   `feature/<issue>-…` branch off `develop`: `core/pyproject.toml`,
   `api/pyproject.toml`, `chat/pyproject.toml`, `accounts/pyproject.toml`
   (`[project] version`)
   and `frontend/package.json` (then
   `cd frontend && npm install --package-lock-only` so `package-lock.json`
   follows). Run `uv lock` afterwards: `uv.lock` records the workspace
   packages' versions, and CI installs with `--locked`, so a stale lock
   fails the PR. The workflow refuses a tag whose version differs from any
   of the five fields. A Lead Maintainer squash-merges that branch into
   `develop`.
2. Open a pull request from `develop` into `main`. A Lead Maintainer
   merges it with a **merge commit**, never squash (ADR-028).
3. Tag the merge commit and push the tag:

   ```bash
   git switch main && git pull
   git tag -a v0.2.0 -m "normly 0.2.0"
   git push origin v0.2.0
   ```

4. Watch the `Images` run. Its summary lists every image digest and the
   `cosign verify` command. A failed run publishes nothing for that tag;
   fix through a `hotfix/<issue>-…` branch into `main` (see *Hotfixes*),
   delete the tag locally and remotely, and tag again.
5. Roll the release out to production by running
   `normly-deploy deploy vX.Y.Z` on the VM. It verifies the signatures,
   takes a backup first and starts the new images; see
   [Operations](operations.md) for the full procedure, including rollback.

## Hotfixes

A critical fix branches off `main` as `hotfix/<issue>-…`. On that branch,
also raise the patch version in the five places from step 1 of *Cutting a
release* (including `npm install --package-lock-only` and `uv lock`); the
workflow refuses a tag that differs from them. A Lead Maintainer merges the
pull request into `main` with a merge commit. Then continue with steps 3–5
above (tag, watch the run, deploy). Afterwards open a pull request from
`main` into `develop` and merge it with a merge commit, so the fix is not
lost with the next release. If that pull request has conflicts, resolve
them on a branch made from `main`, not in the GitHub UI, which would commit
to the protected `main`.

## First publish only

GHCR packages are created private. After the very first successful run,
open each of the six packages (`api`, `chat`, `accounts`, `pipeline`,
`frontend`, `cache`) under the organisation's *Packages*, and set its
visibility to **public** — otherwise `docker compose pull` fails for
anonymous users and the storage counts against the plan's quota.

## Changing model weights

The embedding model and Docling's models are fetched at build time at
fixed commits (`ARG … _REVISION` in `docker/python.Dockerfile`). To move
to a newer revision: look up the commit on huggingface.co, change the
`ARG` default in a commit of its own, and plan a re-embedding of the
knowledge base — vectors from different e5 revisions are not comparable.

## Updating dependencies

Python: `uv lock --upgrade` (or `uv lock --upgrade-package <name>`), run
the test suites, commit `uv.lock`. Base images: refresh the digests in
`docker/python.Dockerfile` and `frontend/Dockerfile` with
`docker buildx imagetools inspect <image>:<tag>`. Frontend: `npm update`
in `frontend/` and commit `package-lock.json`.
