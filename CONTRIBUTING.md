# Contributing to normly

Thanks for wanting to contribute. This document describes how that works in
practice.

Contributions are explicitly **not just code**. Correcting a cross-reference
between Regelwerke, reporting a wrong supersession chain, or suggesting a
source contributes to the most valuable part of the project — practical
domain knowledge is often more useful here than a patch.

## Developer Certificate of Origin (DCO)

normly uses the **DCO** instead of a Contributor License Agreement. You
don't transfer any rights; you only confirm that you're allowed to
contribute the change. The full text is at <https://developercertificate.org/>.

Every commit needs a `Signed-off-by` line for this:

```bash
git commit -s -m "fix: correct supersession chain for DIN EN ISO 9001"
```

The `-s` flag automatically appends:

```
Signed-off-by: First Last <mail@example.org>
```

Name and email must match your git configuration. Pseudonyms are not
allowed — the DCO requires an identifiable person.

Forgot to sign off? Sign afterwards:

```bash
git commit --amend -s          # last commit
git rebase --signoff main      # multiple commits
```

The check runs automatically; without a signature, nothing gets merged.

**Deliberate consequence:** because the rights stay with the contributors, a
later relicensing of the core is permanently ruled out. That's intentional —
see [ADR-003](docs/adr/).

## Process

1. **Talk first, build second.** For anything beyond a bug fix: open an
   issue first. It saves you work that might not end up fitting.
2. **Branch** off `main`, with a descriptive name (`feat/graph-export`,
   `fix/eurlex-parser`).
3. **Commits** following [Conventional Commits](https://www.conventionalcommits.org/):
   `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
4. **Pull request** describing what and why. Link the issue.
5. **Review** by at least one maintainer, green pipeline required.

## Before you open a PR

- [ ] All commits carry `Signed-off-by`
- [ ] Tests pass locally
- [ ] New source files carry the license header
- [ ] No credentials in code, not even in tests or examples
- [ ] For architecture decisions: a draft ADR entry is included

## License header

New files in the core:

```
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors
```

In SDKs and the API specification, use `Apache-2.0` instead.

## Non-negotiable boundaries

These points have legal or strategic reasons. We can't accept PRs that
violate them — even if the code is good. Better to ask in an issue first.

- **No US services** for operations, user data, the standards knowledge
  base, credentials, or production deployment. Exception since ADR-021:
  source code, CI/CD, and the container registry of the free core live on
  GitHub.
- **No scraping of commercially exploited catalog holdings.** Not even if
  they're publicly accessible. New sources need an entry in the source
  registry with an assigned legal basis.
- **No DRM or protection logic in the free core.** Exposed protection code
  is no protection; such components live outside this repository.
- **No account requirement for free content.**
- **No personalized advertising**, no user profiles for advertising
  purposes.
- **No proprietary component in the core.** It must remain buildable,
  testable, and runnable without add-on modules.
- **No direct database access** outside the repository layer.

Detailed rationale: [docs/adr/](docs/adr/).

## Contributions without code

- **Errors in the data** — a wrong reference, an outdated validity status,
  a missing supersession: file an issue with a source. Especially welcome.
- **New sources** — which Regelwerk, which publisher, which legal basis for
  use.
- **Translations and terminology** — normly is meant to work worldwide in
  the long run.
- **Documentation** — if something was unclear, it was unclear.

## Conduct

The [Code of Conduct](CODE_OF_CONDUCT.md) applies.

## Questions

For anything unclear: open an issue. Better one question too many than a
day of wasted work.
