# Developer onboarding

Welcome to normly. This page helps a new contributor find the right part of
the project and understand how to make a change that fits its requirements
and architecture.

> **Project status:** normly is in early development; there is no working
> release or stable API yet. The SRS describes intended behavior, including
> planned work. Check the current code and tests to distinguish implemented
> behavior from requirements that are not implemented yet.

## First steps

1. Read the repository's
   [contribution guide](https://github.com/normly/web-app/blob/develop/CONTRIBUTING.md)
   for the DCO, development setup, pull-request process, and project boundaries.
2. Read [`AGENTS.md`](https://github.com/normly/web-app/blob/develop/AGENTS.md)
   for repository-wide engineering and legal constraints. OpenCode V2 and
   Codex discover the task-specific
   [repository skills](https://github.com/normly/web-app/tree/develop/.agents/skills)
   automatically and load them when relevant. Claude Code can read `AGENTS.md`
   on supported versions, but does not discover skills from `.agents/skills`;
   open the relevant `SKILL.md` manually when using Claude Code.
3. Read the [architecture overview](architecture.md) to find the owning
   component.
4. Look up the relevant requirement in the [SRS index](../srs/README.md) and
   the rationale in the [ADR index](../adr/README.md) before changing
   behavior.

## Get oriented and make a first change

1. Follow the [development setup and checks](https://github.com/normly/web-app/blob/develop/CONTRIBUTING.md#development-setup-and-checks)
   to install the Python workspace and run the test suite for the package you
   will change. Docker is required by tests that use testcontainers. For a
   frontend-only first check, run `cd frontend && npm ci && npm test`.
2. Use the [architecture overview](architecture.md) to find the owning
   component. For example, a document lookup starts at an API router, follows
   the core repository interface, and is covered by the owning package's
   tests. Chat calls the API and accounts services through HTTP clients; it
   does not import their routers.
3. Trace the behavior to its requirement and tests before editing. Normative
   requirements live in the SRS; the ADRs explain durable architectural
   choices. Dated designs and plans in `docs/superpowers/` are useful history,
   not a substitute for checking the current requirement, decision, and code.
4. For a running instance built from your checkout, follow the
   [self-hosting guide](self-hosting.md) and use its build-from-source command
   (`docker compose up -d --build`) rather than pulling the published images.

## How project specifications work

normly keeps requirements, decisions, implementation, and verification
related but distinct:

- The [SRS/SDD](../srs/README.md) describes what the system should do and its
  constraints. Requirement IDs and the index make requirements easy to cite.
- [ADRs](../adr/README.md) record important choices and why they were made,
  including rejected alternatives and consequences.
- Code and tests implement and verify requirements. Guides describe how to
  use and operate the implementation.

For a substantive feature, discuss the proposed behavior in the issue or pull
request before implementation. After agreement, update the existing SRS
requirement or add one if needed; update the ADR only when a significant
architectural or strategic decision needs a durable rationale. Avoid duplicate
specifications that can drift from these sources. See the
[specifications skill](https://github.com/normly/web-app/blob/develop/.agents/skills/specifications/SKILL.md)
for the step-by-step update process.

For development setup, see the
[contribution guide](https://github.com/normly/web-app/blob/develop/CONTRIBUTING.md).
The exact checks run by CI are in
[`.github/workflows/ci.yml`](https://github.com/normly/web-app/blob/develop/.github/workflows/ci.yml).

For package-level testing and branch/PR workflow, see the
[repository-workflow skill](https://github.com/normly/web-app/blob/develop/.agents/skills/repository-workflow/SKILL.md).
