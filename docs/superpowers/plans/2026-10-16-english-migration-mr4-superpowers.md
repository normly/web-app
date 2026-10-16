# English migration, MR 4 (docs/superpowers) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Translate the remaining German working documents under `docs/superpowers/` (about 30 specs and 6 plans, plus German table rows in 3 otherwise English plans) to English, update historical file references to today's names, and close the migration.

**Architecture:** Spec `docs/superpowers/specs/2026-10-15-english-docs-migration-design.md`, MR 4 — one PR (owner decision 2026-10-16). MR 1–3 are merged (PRs #26, #28, #29); the binding glossary is `docs/glossary.md`, section "Terminology (binding)". Order: glossary additions → file renames and path updates (mechanical, so translation diffs stay clean) → translation in batches of related files → closing notes → final review.

**Tech Stack:** Markdown, Zensical docs build, Python 3 check scripts (scratch), `git`.

## Global Constraints

- Branch `docs/english-migration-superpowers` (created from `main` at 865493f; this plan is its first commit). Nothing is pushed and no PR opened without the owner's explicit confirmation. The owner merges PRs; never run `gh pr merge`; never push `main`.
- Only the main session commits. Subagents never run `git add/commit/config/checkout/reset/stash`. Every commit: `git commit -s` plus the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Conventional Commits, English.
- **Binding terminology:** `docs/glossary.md`, section "Terminology (binding)", incl. the three-way withdrawal/retired/withdrawn rule and the capture/acquisition split. Translators read it first.
- **Historical references (owner decision 2026-10-16):** file names and links are updated to today's names; passages quoted from the SRS, the ADRs or CLAUDE.md are replaced by the current English wording of the same passage, verbatim (look it up in `docs/srs/`, `docs/adr/README.md`, `CLAUDE.md`); line numbers stay as historical information.
- **Code blocks stay byte-identical** (except file-name updates done in Task 3). Translate prose, headings, tables, list items and inline text only. Inline code spans stay unchanged.
- **Wiki-link constructs:** the docs build's CI guard expects exactly 3 known `[[…]]` warnings, which come from specs in this directory. Every existing `[[…]]` construct stays byte-identical. Translators' `[[QUESTION n]]` markers must be removed before any commit.
- Faithful translation: no content changes, no corrections; outdated statements stay (these are records of past work). Obvious typos are translated as intended (owner rule). Modal force exact. `Normenausschuss` and `Trägerorganisation` stay German. German statute names stay German with an English gloss at first mention per file.
- Owner decisions for this MR: Auftraggeber → owner; Fassung/Fassungen → version(s) (edition stays for Ausgabestand); Nutzerwunsch/Nutzerentscheidung → owner's request/owner decision.
- A word or passage with no clear rendering: stop and ask the owner (implementers mark `[[QUESTION n]]`, return NEEDS_CONTEXT). Answers go into the glossary in this MR.

## Scratch tooling

`S=/tmp/claude-1000/-home-snake-Dokumente-Projekte-01-normly-normly-app/dacb77f2-8983-4b32-b8a6-e7faa4c32931/scratchpad`. Shell state does not persist; start every command block with `S=<path>`. `$S/parity.py`, `$S/german_left.py`, `$S/docsvenv` exist (else recreate from Task 1 of the MR 1 plan).

Build recipe:
```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app && rm -rf $S/buildtree && mkdir -p $S/buildtree && git ls-files -co --exclude-standard -z | tar --null -cf - -T - | tar -x -C $S/buildtree && (cd $S/buildtree && $S/docsvenv/bin/zensical build > $S/build.log 2>&1); grep -c '^3 issues found' $S/build.log
```
Expected `1` after every task.

## File Structure

| Path | Change |
|---|---|
| `docs/glossary.md` | Task 2: MR 4 terms |
| `docs/superpowers/specs/2026-08-11-datenmodell-referenzgraph-schema-design.md`, `docs/superpowers/plans/2026-08-11-datenmodell-referenzgraph-schema.md` | Task 3: renamed to `…-data-model-reference-graph-schema…` |
| every file under `docs/superpowers/` mentioning old file names | Task 3: names updated |
| German specs and plans (list in Tasks 4–14) | translated |
| `CLAUDE.md`, the migration spec | Task 15: migration closed |

---

### Task 1: Fence checker, originals list, baseline

**Files:**
- Create (scratch): `$S/fences_same.py`

**Interfaces:**
- Produces: `fences_same.py OLD NEW` exits 0 and prints `FENCES OK` when every fenced code block of OLD equals the corresponding block of NEW byte for byte. Used by Tasks 4–14.

- [ ] **Step 1: Write `$S/fences_same.py`**

```python
#!/usr/bin/env python3
"""Compare fenced code blocks of two Markdown files. Usage: fences_same.py OLD NEW"""
import sys


def blocks(path):
    out, cur, inside = [], [], False
    for line in open(path, encoding="utf-8"):
        if line.lstrip().startswith("```"):
            if inside:
                out.append("".join(cur))
                cur = []
            inside = not inside
            continue
        if inside:
            cur.append(line)
    return out


a, b = blocks(sys.argv[1]), blocks(sys.argv[2])
bad = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
if len(a) != len(b) or bad:
    print(f"FENCES DIFFER: counts {len(a)} vs {len(b)}; differing blocks {bad[:10]}")
    sys.exit(1)
print("FENCES OK")
```

- [ ] **Step 2: Self-test and baseline**

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
python3 -I $S/fences_same.py docs/superpowers/plans/2026-10-09-tp4-deployment-automation.md docs/superpowers/plans/2026-10-09-tp4-deployment-automation.md
<build recipe>
grep -n -B1 -A3 -i 'wiki\|\[\[' $S/build.log | head -20
```
Expected: `FENCES OK`; build check `1`; the 3 known warnings are listed — note their files in the report (those files' `[[…]]` constructs must survive translation unchanged).

- [ ] **Step 3: No commit (scratch only)**

---

### Task 2: MR 4 terms in the binding glossary

**Files:**
- Modify: `docs/glossary.md` (section "Terminology (binding)")

- [ ] **Step 1: Add rows (alphabetical by German term, existing format, skip duplicates)**

Owner decisions 2026-10-16:

| German | English |
|---|---|
| Auftraggeber (the project owner) | owner |
| Fassung, Fassungen (of a norm) | version(s) (edition stays for Ausgabestand) |

Standard renderings (controller):

| German | English |
|---|---|
| Befund, Befunde (review) | finding(s) |
| Betriebsguide | operations guide |
| Editionshistorie | edition history |
| Folgearbeit, Folgeaufgabe | follow-up work, follow-up task |
| Implementierungsplan | implementation plan |
| Rechtetor | rights gate |
| Teilprojekt | sub-project |

- [ ] **Step 2: Check and commit**

```bash
git diff --stat
git add docs/glossary.md
git commit -s -m "docs: add MR 4 terminology to the binding glossary

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
Expected before commit: only `docs/glossary.md` changed, +9 rows.

---

### Task 3: Rename the last German file names and update historical paths

**Files:**
- Rename: `docs/superpowers/specs/2026-08-11-datenmodell-referenzgraph-schema-design.md` → `docs/superpowers/specs/2026-08-11-data-model-reference-graph-schema-design.md`; `docs/superpowers/plans/2026-08-11-datenmodell-referenzgraph-schema.md` → `docs/superpowers/plans/2026-08-11-data-model-reference-graph-schema.md`
- Modify: every tracked file mentioning an old name

- [ ] **Step 1: Rename**

```bash
cd /home/snake/Dokumente/Projekte/01_normly/normly-app
git mv docs/superpowers/specs/2026-08-11-datenmodell-referenzgraph-schema-design.md docs/superpowers/specs/2026-08-11-data-model-reference-graph-schema-design.md
git mv docs/superpowers/plans/2026-08-11-datenmodell-referenzgraph-schema.md docs/superpowers/plans/2026-08-11-data-model-reference-graph-schema.md
```

- [ ] **Step 2: Update old file-name tokens repo-wide**

The migration spec and the MR 1–4 plans describe the renames themselves (old → new) and are excluded.

```bash
excl=':!docs/superpowers/specs/2026-10-15-english-docs-migration-design.md :!docs/superpowers/plans/2026-10-15-english-migration-mr1-foundation.md :!docs/superpowers/plans/2026-10-15-english-migration-mr2-adrs.md :!docs/superpowers/plans/2026-10-16-english-migration-mr3-srs.md :!docs/superpowers/plans/2026-10-16-english-migration-mr4-superpowers.md'
files=$(git grep -l -E '(01-einfuehrung|02-produktueberblick|03-anforderungen|05-verifikation|06-anhaenge)\.md|lizenzmodell\.md|normen-graph\.md|normly_(Entwicklungsphasen|Verarbeitungskette)\.svg|datenmodell-referenzgraph-schema' -- . $excl)
echo "$files"
sed -i -E \
  -e 's/01-einfuehrung\.md/01-introduction.md/g' \
  -e 's/02-produktueberblick\.md/02-product-overview.md/g' \
  -e 's/03-anforderungen\.md/03-requirements.md/g' \
  -e 's/05-verifikation\.md/05-verification.md/g' \
  -e 's/06-anhaenge\.md/06-appendices.md/g' \
  -e 's/lizenzmodell\.md/license-model.md/g' \
  -e 's/normen-graph\.md/norm-graph.md/g' \
  -e 's/normly_Entwicklungsphasen\.svg/normly_development-phases.svg/g' \
  -e 's/normly_Verarbeitungskette\.svg/normly_processing-chain.svg/g' \
  -e 's/datenmodell-referenzgraph-schema/data-model-reference-graph-schema/g' \
  $files
```
(`sed` on `$excl`-filtered files; `git grep` pathspec excludes need `-- . ':!path'` form as written.)

- [ ] **Step 3: Verify and commit**

```bash
git grep -n -E '01-einfuehrung|02-produktueberblick|03-anforderungen|05-verifikation|06-anhaenge|lizenzmodell\.md|normen-graph\.md|normly_(Entwicklungsphasen|Verarbeitungskette)|datenmodell-referenzgraph' -- . $excl   # expected: empty
<build recipe>                                                                                            # expected: 1
git add -A
git commit -s -m "docs: rename the last German file names and update historical paths

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tasks 4–14: Translate in batches

After Task 3, save the pre-translation originals once (used by every batch):

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
mkdir -p $S/orig/sp && for f in $(git ls-files 'docs/superpowers/*.md'); do mkdir -p "$S/orig/sp/$(dirname $f)"; cp "$f" "$S/orig/sp/$f"; done
```

| Task | Files (all under `docs/superpowers/`) | Words |
|---|---|---|
| 4 | specs/2026-08-11-data-model-reference-graph-schema-design.md, specs/2026-08-14-ingestion-pipeline-design.md, specs/2026-08-20-accounts-design.md | ~6,600 |
| 5 | specs/2026-08-20-backend-api-design.md, specs/2026-08-20-llm-chat-design.md, specs/2026-08-21-frontend-shell-and-chat-design.md | ~6,900 |
| 6 | specs/2026-08-29-account-profile-management-design.md, specs/2026-08-29-reference-graph-search-and-browse-design.md, specs/2026-08-30-docling-migration-design.md, specs/2026-09-01-baua-adapter-design.md | ~6,900 |
| 7 | specs/2026-09-02-ci-pipeline-design.md, specs/2026-09-05-frontend-shadcn-redesign-design.md, specs/2026-09-06-normtracker-work-entity-design.md, specs/2026-09-07-normtracker-adapter-edition-detection-design.md, specs/2026-09-07-normtracker-document-detail-design.md, specs/2026-09-07-normtracker-semantic-search-design.md | ~7,900 |
| 8 | specs/2026-09-08-normtracker-edition-aware-identity-design.md, specs/2026-09-08-normtracker-watchlist-notification-design.md, specs/2026-09-09-nextjs-upgrade-design.md, specs/2026-09-09-normtracker-frontend-design.md, specs/2026-09-10-accounts-commit-timing-design.md, specs/2026-09-11-documentation-language-policy-english-design.md, specs/2026-09-11-zensical-documentation-site-design.md | ~7,600 |
| 9 | specs/2026-09-23-stackit-deployment-roadmap-design.md, specs/2026-10-01-tp1-containerisation-design.md, specs/2026-10-08-tp2-image-pipeline-design.md | ~7,600 |
| 10 | specs/2026-10-09-tp4-deployment-automation-design.md, specs/2026-10-09-user-data-on-kb-import-design.md, specs/2026-10-10-user-data-lifecycle-design.md | ~5,300 |
| 11 | plans/2026-09-11-zensical-documentation-site.md, plans/2026-10-04-tp1-containerisation.md | prose part of ~11,600 |
| 12 | plans/2026-10-08-tp2-image-pipeline.md, plans/2026-10-10-user-data-lifecycle.md | prose part of ~10,600 |
| 13 | plans/2026-10-09-tp4-deployment-automation.md | prose part of ~11,400 |
| 14 | plans/2026-10-09-user-data-on-kb-import.md; German table rows in plans/2026-08-14-ingestion-pipeline.md, plans/2026-08-21-llm-chat.md; any German prose left in plans/2026-09-11-documentation-language-policy-english.md | prose part of ~6,700 + rows |

Each batch task:

**Files:** Modify only the files in its row.

- [ ] **Step 1: Translate the files** with this brief (verbatim in every implementer prompt):

> Translate the given German working documents (specs/plans of the normly project) to English in place. Read `docs/glossary.md`, section "Terminology (binding)", first; its renderings are binding (incl. the withdrawal/retired/withdrawn rule and capture vs acquisition). Translate prose, headings, tables, list items; keep every fenced code block, inline code span, `[[…]]` construct, link target, ID, date, number and path byte-identical. Passages quoted from the SRS, the ADRs or CLAUDE.md: replace them with the current English wording of the same passage, verbatim (look it up in `docs/srs/`, `docs/adr/README.md`, `CLAUDE.md`); keep line numbers as they are. Faithful translation only: no content changes, no corrections, outdated statements stay; obvious typos are translated as intended (list each). Modal force must stay exact. `Normenausschuss` and `Trägerorganisation` stay German. Auftraggeber → owner; Fassung → version; Nutzerwunsch → owner's request. Already-English specs/plans in the same directory and the guides (`docs/guide/*`) are style and terminology references for the same topics. Do NOT run git commands that change state. If any word or passage has no clear rendering, leave a `[[QUESTION n]]` marker, list it in your report and final reply (German text, context, 1–3 candidates), finish the rest, and return NEEDS_CONTEXT.

- [ ] **Step 2: Resolve QUESTIONS with the owner; add answers to the glossary; remove all markers** (`grep -rn 'QUESTION' <files>` → empty)

- [ ] **Step 3: Checks per file**

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
for f in <files>; do echo "== $f"; python3 -I $S/parity.py $S/orig/sp/$f $f; python3 -I $S/fences_same.py $S/orig/sp/$f $f; done
python3 -I $S/german_left.py <files>
git diff --stat
<build recipe>
```
Expected: `PARITY OK` and `FENCES OK` for every file; no suspect lines except justified quoted German (product UI strings, German source text in fixtures — listed in the report); only the batch's files changed; build check `1`.

- [ ] **Step 4: Commit** — `docs: translate <short description> to English` (e.g. "translate the August specs (data model, ingestion, accounts) to English"), with `-s` and the Co-Authored-By trailer.

---

### Task 15: Close the migration

**Files:**
- Modify: `CLAUDE.md` (Language section), `docs/superpowers/specs/2026-10-15-english-docs-migration-design.md` (status line)

- [ ] **Step 1: `CLAUDE.md`** — delete the whole paragraph that starts "Migration in progress (2026-10-15):" (and one adjacent blank line). Change nothing else. Use the Edit tool.

- [ ] **Step 2: Migration spec** — change its status line to `Status: approved by the owner, 2026-10-15; completed 2026-10-16 (PRs #26, #28, #29 and the MR 4 PR)`.

- [ ] **Step 3: Repo-wide German check**

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
python3 -I $S/german_left.py $(git ls-files '*.md') | grep -v '^docs/glossary.md' | cut -c1-150
```
Expected: only justified quoted German (product UI strings, the DE slogan in `docs/srs/01-introduction.md`, the two quoted German UI strings in ADR-026, quoted German in fixtures/test-data descriptions). List every hit in the report with its justification.

- [ ] **Step 4: Commit** — `docs: close the English migration`, with `-s` and the trailer.

---

### Task 16: Final verification and review

- [ ] **Step 1: Invoke `superpowers:verification-before-completion` and run fresh:** clean tree; parity + fences for every translated file against `$S/orig/sp/`; the repo-wide German check from Task 15; build check `1`; no old file names (Task 3 grep).
- [ ] **Step 2: Whole-branch review** on the most capable model: terminology consistency across all translated specs/plans and against the glossary, ADRs, SRS and guides; quoted SRS/ADR passages match the current English wording; no content changes; code blocks untouched. One fix wave, one scoped re-review.
- [ ] **Step 3: Hand over to the owner** — results, open questions; ask before pushing and opening the PR.
