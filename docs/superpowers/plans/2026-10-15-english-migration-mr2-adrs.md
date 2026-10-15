# English migration, MR 2 (ADRs) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Translate `docs/adr/README.md` (all 27 ADRs and the open-items table) to English, close the migration in ADR-020 with an addendum, and keep every link into the ADRs working.

**Architecture:** Spec `docs/superpowers/specs/2026-10-15-english-docs-migration-design.md`, MR 2. MR 1 (PR #26) is merged and established the binding glossary (`docs/glossary.md`, section "Terminology (binding)"). This MR first adds the ADR-specific terms to that glossary, then translates the ADR file in five sequential chunks (one file, so no parallel work), then fixes the heading anchors that change with the translation.

**Tech Stack:** Markdown, Zensical docs build, Python 3 check scripts (scratch), `git`.

## Global Constraints

- Branch `docs/english-migration-adr` (created from `main` at 862049e; this plan is its first commit). Nothing is pushed and no PR opened without the owner's explicit confirmation. The owner merges PRs; never run `gh pr merge`.
- Only the main session commits. Subagents never run `git add/commit/config/checkout/reset/stash`. Every commit: `git commit -s` plus the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Conventional Commits, English.
- **Binding terminology:** `docs/glossary.md`, section "Terminology (binding)", after Task 2 has extended it. Every translator reads that section first. Core pairs: Norm→norm, Regelwerk→standards, Herausgeber→publisher, Referenzgraph→reference graph, Wissensbasis/Wissensbestand→knowledge base, Rechteklassifikation→rights classification, Lizenzklassifikation→license classification, Rechtsraum→jurisdiction, Ausgabestand→edition, Quelllieferung→source delivery, Abstammung→lineage, Herkunft→provenance, Rücknahme/Rückzug→withdrawal, Auslieferung→shipping, Ausspielung→output, Bestand→collection, Sicherung→backup, Trägerschaft→stewardship. `Normenausschuss` and `Trägerorganisation` stay German.
- A word or passage with no clear rendering under the glossary: stop and ask the owner (implementers mark `[[QUESTION n]]` and return NEEDS_CONTEXT). Every answer is added to the glossary table in a follow-up commit of the same MR.
- Faithful translation: no content changes, no corrections, outdated statements stay outdated (ADRs are a historical record). Modal force exact (muss→must, soll→should, darf nicht→must not, nur→only, nie→never, kein→no). "bzw." → "respectively" where it maps items, "or" only where it is a genuine alternative.
- Unchanged: ADR numbers and the `## ADR-0NN — Title` heading shape (em dash), dates, `REQ-…` IDs, code spans, file paths, product/vendor names, quoted command output. German statute names stay German with an English gloss at first mention in this file (e.g. "§ 5 UrhG (German Copyright Act)"). German quotation marks „…" become "…".
- References to CLAUDE.md section names use the current English headings (e.g. „Sprache" → "Language", „Identifikatoren" → "Identifiers", „Nicht verhandelbar" → "Non-negotiable").
- Links into the still-German SRS (`docs/srs/03-requirements.md#req-…`) keep their anchors unchanged (MR 3 handles them).
- The repo's `site/` may be root-owned: always build from a scratch copy (Task 1 recipe).

## Scratch tooling

`S=/tmp/claude-1000/-home-snake-Dokumente-Projekte-01-normly-normly-app/dacb77f2-8983-4b32-b8a6-e7faa4c32931/scratchpad`. Shell state does not persist; start every command block with `S=<path>`. `$S/parity.py`, `$S/german_left.py` and `$S/docsvenv` exist from MR 1; if they are missing, recreate them from Task 1 of `docs/superpowers/plans/2026-10-15-english-migration-mr1-foundation.md`.

Build recipe (used by several tasks):
```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app && rm -rf $S/buildtree && mkdir -p $S/buildtree && git ls-files -co --exclude-standard -z | tar --null -cf - -T - | tar -x -C $S/buildtree && (cd $S/buildtree && $S/docsvenv/bin/zensical build > $S/build.log 2>&1); grep -c '^3 issues found' $S/build.log
```
Expected `1` (the CI guard's baseline of 3 known issues).

## File Structure

| Path | Change |
|---|---|
| `docs/glossary.md` | Task 2: ADR terms added to the binding table |
| `docs/adr/README.md` | Tasks 3–7: translated in five chunks; Task 8: ADR-020 addendum |
| `CLAUDE.md` | Task 8: Language section migration note updated |
| `docs/index.md` | Task 8: German-only note narrowed to the SRS |
| every tracked file linking `adr/README.md#…` | Task 9: anchors rewritten to the new English slugs |

---

### Task 1: Chunk helper and baseline

**Files:**
- Create (scratch, not committed): `$S/adr_chunk.py`

**Interfaces:**
- Produces: `adr_chunk.py FILE FIRST LAST` prints the part of an ADR file from the heading `## ADR-<FIRST>` up to (not including) the heading `## ADR-<LAST+1>` or the first `## ` heading that is not an ADR. `FIRST=0` starts at line 1 (title and intro). Used by Tasks 3–7 for parity checks.

- [ ] **Step 1: Write `$S/adr_chunk.py`**

```python
#!/usr/bin/env python3
"""Print one chunk of the ADR file. Usage: adr_chunk.py FILE FIRST LAST

FIRST=0 starts at line 1. The chunk ends before '## ADR-<LAST+1>' or before
the first '## ' heading that is not an ADR heading, whichever comes first.
"""
import re
import sys

path, first, last = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
out, on = [], first == 0
for line in open(path, encoding="utf-8"):
    m = re.match(r"## ADR-(\d{3}) ", line)
    if m:
        n = int(m.group(1))
        if n == first:
            on = True
        elif n > last:
            break
    elif line.startswith("## ") and on and not line.startswith("## ADR-"):
        if last < 999:
            break
    if on:
        out.append(line)
sys.stdout.write("".join(out))
```

Note: `LAST=999` means "to the end of the file" (includes the open-items section).

- [ ] **Step 2: Self-test**

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
python3 -I $S/adr_chunk.py docs/adr/README.md 0 7 | head -3
python3 -I $S/adr_chunk.py docs/adr/README.md 0 7 | tail -3
python3 -I $S/adr_chunk.py docs/adr/README.md 25 999 | grep -c '^## '
for r in "0 7" "8 14" "15 20" "21 24" "25 999"; do python3 -I $S/adr_chunk.py docs/adr/README.md $r | wc -w; done
```
Expected: first line `# normly — Entscheidungsdokumentation (ADR)`; the tail of chunk 0–7 ends before `## ADR-008`; chunk 25–999 contains 4 `## ` headings (ADR-025, 026, 027, Offene Punkte); the five word counts sum to the file's ~10,100 words.

- [ ] **Step 3: Save the original and the baseline anchors**

```bash
mkdir -p $S/orig && git show main:docs/adr/README.md > $S/orig/adr-README.md
# Build baseline and keep the German heading ids in order
<build recipe>
python3 -c "import re,sys; print('\n'.join(re.findall(r'<h2 id=\"([^\"]+)\"', open(sys.argv[1],encoding='utf-8').read())))" $S/buildtree/site/adr/index.html > $S/adr-ids-de.txt
wc -l $S/adr-ids-de.txt; head -3 $S/adr-ids-de.txt
```
Expected: build check prints `1`; 28 ids (27 ADRs + open items), first `adr-001-open-core-modell-statt-white-label-produkt`. If the path `site/adr/index.html` does not exist, find the built ADR page with `ls $S/buildtree/site/adr*` and use that path here and in Task 9.

- [ ] **Step 4: No commit (scratch only)**

---

### Task 2: Add the ADR terms to the binding glossary

**Files:**
- Modify: `docs/glossary.md` (section "Terminology (binding)")

- [ ] **Step 1: Add these rows to the table, keeping alphabetical order by the German term and the existing row format (no duplicates of rows already there)**

Owner decisions 2026-10-15 (MR 2 preparation):

| German | English |
|---|---|
| Partnerschaftsleiter / Volltext-Sprung (ADR-013) | partnership ladder / full-text leap |
| Kennung (record ID, e.g. "zurückgezogene Kennungen", "Google-Kennung") | ID |
| Bezeichner (of a norm, e.g. "DIN EN ISO 9001") | designation (code: `DocumentDesignation`) |
| Bezeichner (programming sense) | identifier |
| Identifikator, Identifikatorschema | identifier, identifier scheme |
| Herkunftsadresse | client IP address |
| Alterung (of tombstones) | expiry |

Standard renderings (controller, consistent with code and existing English docs):

| German | English |
|---|---|
| Aufbewahrung | retention |
| Aufräumbefehl | cleanup command |
| beschlossen / favorisiert / offen (ADR status) | accepted / preferred / open |
| abgelöst durch / ersetzt / ergänzt (ADR status) | superseded by / replaces / amends |
| Beobachtungsliste | watchlist |
| Betreiber | operator |
| Entscheidungsdokumentation | architecture decision records |
| Kontingent | quota |
| Kontobezug | account reference |
| Kopierschutz | copy protection |
| kryptographisches Löschen | cryptographic erasure |
| Löschprotokoll | deletion log |
| Massenextraktion | bulk extraction |
| Nachverfolgbarkeit | traceability |
| Neulieferung | re-delivery |
| Offene Punkte | Open items |
| Ratenbegrenzung | rate limiting |
| Schlüsselzeremonie | key ceremony |
| Selbsthoster | self-hosters |
| Umsetzung (ADR label) | Implementation |
| Nicht betroffen (ADR label) | Not affected |
| Verworfen (ADR label) | Rejected |
| Widerruf | revocation (code: `revoked_at`) |

- [ ] **Step 2: Check**

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
git diff --stat; awk '/^## Terminology \(binding\)/{f=1} f' docs/glossary.md | grep -c '^| '
```
Expected: only `docs/glossary.md` changed; the table row count grew by the number of new rows (no duplicates).

- [ ] **Step 3: Commit**

```bash
git add docs/glossary.md
git commit -s -m "docs: add ADR terminology to the binding glossary

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tasks 3–7: Translate the ADR file in five chunks

Each chunk task follows the same steps; only the range differs. The translator edits `docs/adr/README.md` in place, only inside its range.

| Task | Range (`adr_chunk.py` args) | Content | Notes |
|---|---|---|---|
| 3 | `0 7` | Title, intro, ADR-001 – ADR-007 | Intro "Status je Eintrag" list uses the ADR status renderings |
| 4 | `8 14` | ADR-008 – ADR-014 | ADR-009 "anerkannter Stand der Technik" → recognized state of the art; ADR-012 legal categories; ADR-013 title per glossary; ADR-014 cryptographic erasure |
| 5 | `15 20` | ADR-015 – ADR-020 | ADR-020: translate faithfully as it stands, including its 2026-09-14 addendum; its references to CLAUDE.md headings use the English names. The new addendum is Task 8, not here |
| 6 | `21 24` | ADR-021 – ADR-024 | Operations-heavy: backup/rollback terms, keep commands and paths verbatim |
| 7 | `25 999` | ADR-025 – ADR-027, Open items | Tables with retention periods; "Offene Punkte" → "Open items" |

**Files:**
- Modify: `docs/adr/README.md` (only the chunk's range)

**Interfaces:**
- Consumes: `$S/adr_chunk.py`, `$S/parity.py`, `$S/german_left.py`, `$S/orig/adr-README.md`, the glossary from Task 2.
- Produces: the translated range. Headings keep `## ADR-0NN — ` so later chunks and Task 9 can find them.

- [ ] **Step 1: Translate the range**

Translation brief (verbatim in every implementer prompt):

> Translate the given range of `docs/adr/README.md` from German to English in place. Read `docs/glossary.md`, section "Terminology (binding)", first; its renderings are binding. Faithful translation only: do not add, drop, reword for style, or correct content; outdated statements stay as they are (ADRs are history). Keep Markdown structure, tables, links, code spans, IDs, dates and numbers exactly; keep the heading shape `## ADR-0NN — Title`. Modal force must stay exact. `Normenausschuss` and `Trägerorganisation` stay German. German statute and standard names stay German with an English gloss in parentheses at first mention in the file. References to CLAUDE.md section names use its current English headings. Links into `docs/srs/…` keep their anchors. Do NOT run git commands that change state. If any word or passage has no clear rendering under these rules, do not guess: leave a `[[QUESTION n]]` marker and list it in your report and final reply (German text, context, 1–3 candidates), finish the rest, and return NEEDS_CONTEXT.

- [ ] **Step 2: Resolve QUESTIONS with the owner; add each answer to the glossary table; remove the markers**

Run: `grep -n 'QUESTION' docs/adr/README.md` — Expected: no output.

- [ ] **Step 3: Checks for the range**

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
python3 -I $S/adr_chunk.py $S/orig/adr-README.md <FIRST> <LAST> > $S/chunk-de.md
python3 -I $S/adr_chunk.py docs/adr/README.md <FIRST> <LAST> > $S/chunk-en.md
python3 -I $S/parity.py $S/chunk-de.md $S/chunk-en.md
python3 -I $S/german_left.py $S/chunk-en.md
git diff --stat
```
Expected: `PARITY OK`; no suspect lines except quoted German that the rules keep (statute names, `Normenausschuss`, `Trägerorganisation`) — each remaining line is listed and justified in the report; only `docs/adr/README.md` changed, and only inside the range (check with `git diff -U0 docs/adr/README.md | grep '^@@'` against the range's line numbers).

Note for Task 7 only: `LAST=999` includes the "Offene Punkte"/"Open items" section; for the chunk-de extraction the German heading is "Offene Punkte", for chunk-en "Open items" — both are included because LAST=999 runs to the end.

- [ ] **Step 4: Commit**

```bash
git add docs/adr/README.md
git commit -s -m "docs: translate ADR-<FIRST>–ADR-<LAST> to English

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
(Task 3: "translate ADR title, intro and ADR-001–ADR-007"; Task 7: "translate ADR-025–ADR-027 and open items".)

---

### Task 8: Close the migration in ADR-020 and update the pointers

**Files:**
- Modify: `docs/adr/README.md` (end of ADR-020, before its closing `---`)
- Modify: `CLAUDE.md` (Language section)
- Modify: `docs/index.md` (German-only note)

- [ ] **Step 1: Append this addendum to ADR-020, after the translated 2026-09-14 addendum**

```markdown
**Addendum 2026-10-15 — complete migration:** At the owner's request,
everything in the repository moves to English, including `CLAUDE.md` and
the working documents under `docs/superpowers/`. The exception for
`docs/superpowers/` and `CLAUDE.md` stated above no longer applies. The
migration runs in four merge requests: foundation (root files,
`CLAUDE.md`, diagrams, file names, binding glossary), the ADRs (this
document), the SRS, and `docs/superpowers/`. Terminology is binding and
recorded in `docs/glossary.md`, section "Terminology (binding)". Design:
`docs/superpowers/specs/2026-10-15-english-docs-migration-design.md`.
```

- [ ] **Step 2: Update the Language section of `CLAUDE.md`**

Replace the arrow tail
```
end users) is unaffected. → ADR-020 (addendum pending in the ADR
translation; the decision is recorded in
`docs/superpowers/specs/2026-10-15-english-docs-migration-design.md`)
```
with
```
end users) is unaffected. → ADR-020
```
and in the "Migration in progress" paragraph remove `docs/adr/` from the list of still-German locations (keep `docs/srs/` and `docs/superpowers/`, fix the grammar of the list). Change nothing else in `CLAUDE.md`.

- [ ] **Step 3: Update `docs/index.md`**

Replace
```
Architecture decisions and Requirements are currently German-only; the
rest of the site is in English, and full translation is tracked
separately.
```
with
```
The Requirements (SRS) are currently German-only; the rest of the site
is in English, and their translation is tracked separately.
```

- [ ] **Step 4: Check and commit**

```bash
S=<path>; python3 -I $S/german_left.py CLAUDE.md docs/index.md; git diff --stat
git add docs/adr/README.md CLAUDE.md docs/index.md
git commit -s -m "docs: close the English migration in ADR-020 and update pointers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
Expected before commit: no suspect lines; exactly these 3 files changed.

---

### Task 9: Rewrite anchors into the ADRs

The translated headings produce new slugs (e.g. `#adr-010-auslieferung-als-container-daten-getrennt-vom-image` → `#adr-010-shipping-as-containers-…`). All inbound links must follow, including those in `docs/superpowers/` (otherwise the docs build reports new broken anchors and the CI guard fails).

**Files:**
- Modify: every tracked file containing `adr/README.md#` (currently: `docs/glossary.md`, `docs/concepts/license-model.md`, `docs/concepts/norm-graph.md`, `docs/guide/self-hosting.md`, `docs/guide/releasing.md`, `docs/guide/operations.md`, and several plans under `docs/superpowers/plans/`)

- [ ] **Step 1: Build and extract the new ids**

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
<build recipe>
python3 -c "import re,sys; print('\n'.join(re.findall(r'<h2 id=\"([^\"]+)\"', open(sys.argv[1],encoding='utf-8').read())))" $S/buildtree/site/adr/index.html > $S/adr-ids-en.txt
paste -d' ' $S/adr-ids-de.txt $S/adr-ids-en.txt > $S/adr-id-map.txt; cat $S/adr-id-map.txt
```
Expected: 28 lines, each pairing the same ADR number (`adr-0NN-…` on both sides; last line the open-items ids). Abort if any line pairs different numbers.

- [ ] **Step 2: Rewrite the anchors (exact `#old-id` tokens only)**

```bash
files=$(git grep -l 'README\.md#adr-\|README\.md#offene-punkte')
python3 -I - $S/adr-id-map.txt $files <<'EOF'
import sys
pairs = [l.split() for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
for path in sys.argv[2:]:
    s = open(path, encoding="utf-8").read()
    t = s
    for old, new in pairs:
        t = t.replace("README.md#" + old + ")", "README.md#" + new + ")")
        t = t.replace("README.md#" + old + "`", "README.md#" + new + "`")
        t = t.replace("README.md#" + old + "\n", "README.md#" + new + "\n")
        t = t.replace("README.md#" + old + " ", "README.md#" + new + " ")
    if t != s:
        open(path, "w", encoding="utf-8").write(t)
        print("updated", path)
EOF
```
The suffix characters guard against replacing a prefix of a longer id. The truncated link `adr/README.md#adr-010-` in `docs/superpowers/plans/2026-09-11-documentation-language-policy-english.md:369` is prose about a prefix, not a link; leave it.

- [ ] **Step 3: Verify**

```bash
git grep -n -o -E 'README\.md#adr-[a-z0-9-]+' | sed 's/.*#//' | sort -u > $S/used-ids.txt
grep -v -x -F -f $S/adr-ids-en.txt $S/used-ids.txt
<build recipe>
```
Expected: the `grep -v` prints only `adr-010-` (the prose prefix above) or nothing; the build check prints `1`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -s -m "docs: point ADR links to the English heading anchors

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Final verification and review

- [ ] **Step 1: Invoke `superpowers:verification-before-completion` and run fresh**

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
git status --short                                   # expected: clean
git log --oneline main..HEAD                         # plan + Task 2-9 commits (+ glossary answer commits)
python3 -I $S/parity.py $S/orig/adr-README.md docs/adr/README.md   # see note
python3 -I $S/german_left.py docs/adr/README.md     # expected: only justified quoted German
grep -c '^## ADR-0' docs/adr/README.md              # expected: 27
<build recipe>                                       # expected: 1
```
Note: whole-file parity differs from the original by exactly the ADR-020 addendum (one paragraph, no headings/lists/tables), so headings, tables, list items, code fences and IDs must still match; link targets match after anchor mapping is ignored (parity compares paths only).

- [ ] **Step 2: Whole-branch review** on the most capable model, against the spec, this plan and the glossary: meaning drift (especially ADR-009, -012, -014, -015, -017, -020, -026, -027), terminology consistency with the glossary and the already-English docs, anchor integrity, the ADR-020 addendum. One fix wave for its findings, one scoped re-review.

- [ ] **Step 3: Hand over to the owner** — results, open questions, and ask before pushing and opening the PR. After merge: write the MR 3 plan (SRS).
