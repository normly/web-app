# Contribution process — design

Date: 2026-10-18
Status: approved by the owner in brainstorming, 2026-10-18
Issue: #39 · Branch: `feature/39-contribution-process` (off `develop`)

## Background

normly is no longer a one-person project: Tobias Haarhoff now works on it
too, and the repository is meant to take outside contributions. The owner
wrote a contribution guide (issue → requirement → code → PR → merge, with
`develop`/`main` branching). This design fits that guide into the
repository as it is today.

What exists today:

- `CONTRIBUTING.md` describes DCO, the development setup, a five-step
  process (branch off `main`), license headers, the non-negotiable
  boundaries and contributions without code. It claims "the check runs
  automatically" for the DCO sign-off; no such check exists.
- `README.md` has a short "Contributing" section.
- `GOVERNANCE.md` names the roles Contributor, Maintainer and Technical
  lead; the legal form of the Trägerorganisation is open.
- `MAINTAINERS.md` lists every area as *(to be added)*.
- CI (`.github/workflows/ci.yml`) runs only for `main`. The image workflow
  builds `edge` on every push to `main` and releases on `vX.Y.Z` tags.
- No PR template, no issue templates, no CODEOWNERS. `main` is not
  protected.

The owner has already created `develop` from `main` on GitHub and made it
the default branch.

## Decisions

| # | Decision |
|---|---|
| D1 | Branching as in the guide: `main` (production, tagged releases), `develop` (integration, default branch), work branches `feature/<issue>-…`, `fix/<issue>-…`, `hotfix/<issue>-…`. Documentation work counts as a feature. |
| D2 | **Only Lead Maintainers merge**, into `develop` and into `main`, including hotfixes and the back-merge `main` → `develop`. Maintainers approve requirements and review; they do not merge. |
| D3 | A Lead Maintainer may merge their own PR after green CI; no second review is required. |
| D4 | Lead Maintainers: Jan Wokittel (@Sn4kez) and Tobias Haarhoff (@TobiasHaarhoff). The role is called **Lead Maintainer** everywhere; "Technical lead" is retired. |
| D5 | The Trägerorganisation is **normly e.V.** If the two Lead Maintainers disagree, the board of normly e.V. decides. |
| D6 | "Spec" in the guide means the **requirements** in `docs/srs/03-requirements.md` (REQ IDs with acceptance criteria). A feature PR adds or changes its REQ in the same PR. Requirements get no status field; the guide's "status `accepted` on merge" rule is dropped. |
| D7 | Merge methods: work branches → `develop` by **squash** (one commit per PR); `develop` → `main` (release), `hotfix/…` → `main` and the back-merge `main` → `develop` by **merge commit**. Squashing a release would give `main` commits `develop` does not know and break every later back-merge. |
| D8 | DCO sign-off is manual: every contributor uses `git commit -s`. There is no automatic DCO check. The merging Lead Maintainer makes sure the `Signed-off-by` lines survive in the squash commit message. |
| D9 | AI involvement is recorded as `Assisted-by: <tool>` in the commit and stated in the PR — never as `Co-Authored-By` (GitHub would show the tool as an author) and never as `Signed-off-by`. |
| D10 | The `edge` image keeps being built **only from `main`**. With `develop` in place, `main` changes only on releases and hotfixes, so `edge` tracks production, not integration. |
| D11 | The PR template keeps the line `Issue: #` (named after the GitHub feature). Closing the issue is done by linking it in the PR's *Development* field or by hand. |

## Changes in this PR

### `CONTRIBUTING.md` — rewritten along the guide

Structure: Principles · Roles · Workflow (flowchart) · Fix vs. Feature ·
Branches (table + gitGraph) · Commits · Pull requests · Working with AI ·
Scaling · then the kept sections.

Adapted from the guide:

- Paths: requirements in `docs/srs/03-requirements.md`, ADRs in
  `docs/adr/README.md` (not `specs/` and `adr/`).
- Roles table: Maintainer = requirement approval and review; Lead
  Maintainer = architecture (ADRs), **every merge**, releases, conflicts
  (D2). Founding team → normly e.V. (D5).
- Workflow diagram: step 5 reads "Lead Maintainer → develop / main".
- Fix/Feature table without the status rule (D6).
- Branches: merge methods per D7; hotfix back-merge described.
- Commit example ends with `Signed-off-by` and `Assisted-by` (D9).
- Scaling table: "Self-merge on green CI" becomes "Lead Maintainer merges
  after green CI"; external PRs: review by one Maintainer, merge by a Lead
  Maintainer.

Kept from today's file: why contributions are not just code, the DCO
section (pseudonyms not allowed, signing afterwards, the relicensing
consequence) — minus the false "the check runs automatically" sentence,
replaced by D8 — the development setup, the license header, the
non-negotiable boundaries, contributions without code, conduct, questions.
"Before you open a PR" moves into the PR template.

### `README.md`

The "Contributing" section gets a short version of the workflow (issue →
requirement → branch → PR → Lead Maintainer merge), the gitGraph from the
guide, the DCO commit example, and the links to `CONTRIBUTING.md` and
`SECURITY.md`.

### `.github/pull_request_template.md`

```markdown
Issue: #    Spec: REQ-XXX-NNN    Type: Fix | Feature | Hotfix
Target: develop (hotfix: main)

**What and why**

**Acceptance criteria**
- [ ] … met by …

- [ ] Tests added
- [ ] Documentation updated (README, guides, code reference)
- [ ] ADR draft included, if architecture, data model or interfaces change
- [ ] Breaking change or migration: no | yes (described above)
- [ ] New data source: register entry with category A–D and legal basis
- [ ] New dependencies license-checked
- [ ] New source files carry the license header
- [ ] No credentials in code, not even in tests or examples
- [ ] DCO sign-off on every commit
- [ ] AI used: no | yes (tool, recorded as `Assisted-by:`)
```

### `.github/ISSUE_TEMPLATE/` (issue forms)

- `bug.yml` — what happened, expected, steps, version/instance.
- `feature.yml` — problem, goal, existing REQ ID or proposal for a new one.
- `data-error.yml` — affected norm/standard, what is wrong, **source**
  (required).
- `new-source.yml` — publisher, what it contains, category A–D (required),
  legal basis, confirmation that it is not a commercially exploited catalog
  (required checkbox).
- `config.yml` — blank issues off; contact link to `SECURITY.md` for
  vulnerabilities.

### `.github/CODEOWNERS`

`* @Sn4kez @TobiasHaarhoff`. Per-module owners come later (Scaling table).

### `GOVERNANCE.md`

"Technical lead" → "Lead Maintainer" (two people, D4); the
Trägerorganisation is normly e.V.; tie-break by the board (D5); merging
only by Lead Maintainers (D2).

### `MAINTAINERS.md`

Lead Maintainers: Jan Wokittel (@Sn4kez), Tobias Haarhoff
(@TobiasHaarhoff). The area rows stay *(to be added)*.

### `docs/adr/README.md` — ADR-028

"Branching and merge model: `develop` integration, Lead Maintainer
merges". Records D1, D2, D3, D7, D8, D10, with the rejected alternative
(GitHub Flow with `main` only — rejected because outside contributions
need an integration branch that is not production).

### `docs/guide/releasing.md`

The release is a PR `develop` → `main` (merge commit), then the tag on
`main`; `edge` still comes from `main` only (D10); hotfixes and the
back-merge.

### `.github/workflows/ci.yml`

`pull_request` and `push` also for `develop`. `images.yml` stays
unchanged (D10).

### `CLAUDE.md`

In "For every code change": PRs target `develop`; only Lead Maintainers
merge; the line "No direct push to `main` — merge request with review and
a green pipeline" becomes "No direct push to `main` or `develop` — pull
request with a green pipeline, merged by a Lead Maintainer" (D3); AI
involvement as `Assisted-by:` (never `Co-Authored-By` or
`Signed-off-by`).

### `.claude/settings.json`

Claude Code's attribution set so that commits end with
`Assisted-by: Claude Code` instead of a `Co-Authored-By` trailer and PRs
get no generated footer. Applies to every Lead Maintainer using Claude Code
in this repository. The exact setting key is verified during
implementation.

## Out of scope — GitHub settings (owner, checklist in the PR)

1. Permissions: write/admin only for Lead Maintainers; others at most
   *Triage*, contributing through forks. Review whether @erolabzait keeps
   admin.
2. Pull request settings: merge commits on, squash on with "Default to pull
   request title and commit details", rebase off, auto-delete head
   branches on.
3. Rulesets without bypass list, both: restrict deletions, block force
   pushes, require a PR (0 approvals), require the seven CI jobs
   (`test-accounts`, `test-api`, `test-chat`, `test-core`,
   `test-frontend`, `test-docs`, `test-scripts`).
   - `develop`: squash and merge allowed.
   - `main`: merge only.
   Required checks on `develop` are switched on after this PR is merged.
4. Label `process` (the guide requires it for changes to
   `CONTRIBUTING.md`); this PR carries it.
5. The commit identity: real name in `git config user.name`, and the
   commit e-mail verified on the GitHub account so commits link to the
   person.

Follow-up, not in this PR: an automatic DCO check, per-module CODEOWNERS.

## Verification

- `zensical build` stays green (the docs site includes `docs/adr/` and
  `docs/guide/`).
- Mermaid flowchart and gitGraph render in the GitHub preview of the
  pushed branch.
- The PR template and issue forms appear on GitHub (issue forms validate
  only on the default branch — checked after merge).
- CI runs for this PR against `develop`.
- No remaining "Technical lead", `specs/`, "self-merge" or
  `Co-Authored-By` instruction in the changed files (grep).
