# English migration, MR 3 (SRS) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Translate the SRS (`docs/srs/`: README, chapters 01, 02, 03, 05, 06; ~13,300 words) to English and keep every link into it working.

**Architecture:** Spec `docs/superpowers/specs/2026-10-15-english-docs-migration-design.md`, MR 3. MR 1 (PR #26) and MR 2 (PR #28) are merged; the binding glossary is `docs/glossary.md`, section "Terminology (binding)". This MR first adds the SRS terms to the glossary, then translates chapters 01/02/05/06 in one task and chapter 03 (requirements, ~9,900 words) in five sequential chunks, then translates the SRS index (`docs/srs/README.md`) and rewrites its 78 requirement anchors, then updates the pointers.

**Tech Stack:** Markdown, Zensical docs build, Python 3 check scripts (scratch), `git`.

## Global Constraints

- Branch `docs/english-migration-srs` (created from `main` at 8f5be8b; this plan is its first commit). Nothing is pushed and no PR opened without the owner's explicit confirmation. The owner merges PRs; never run `gh pr merge`. Never push `main`.
- Only the main session commits. Subagents never run `git add/commit/config/checkout/reset/stash`. Every commit: `git commit -s` plus the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Conventional Commits, English.
- **Binding terminology:** `docs/glossary.md`, section "Terminology (binding)", as extended by Task 2. Every translator reads that section first. Already-English sources for the same facts (use their wording for the same concept): `CLAUDE.md`, `docs/adr/README.md` (ADRs cite and mirror many requirements), `docs/glossary.md` definitions, `docs/guide/*`, `docs/concepts/*`.
- A word or passage with no clear rendering under the glossary: stop and ask the owner (implementers mark `[[QUESTION n]]` and return NEEDS_CONTEXT). Every answer is added to the glossary table in the same MR.
- Faithful translation: no content changes, no corrections; outdated statements stay. Modal force exact (muss→must, soll→should, kann→can/may, darf nicht→must not, nur→only, nie→never, kein→no). "bzw." → "respectively" only where it maps items, otherwise "or".
- Requirement block shape stays: `### REQ-XXX-NNN — Title` or `#### REQ-XXX-NNN — Title` (the original uses both levels — keep each heading at its level), then the fields in their order. Field labels: **Statement**, **Rationale** (already English), **Acceptance criteria** (Akzeptanzkriterium), **Acceptance test** (Abnahmekriterium), **Further information** (Weitere Informationen), **Status**, **Important** (Wichtig), "Stand (date)" → "As of (date)". Trailing two-space line breaks after field lines are kept.
- Unchanged: `REQ-…` IDs, ADR numbers, chapter numbers, dates, code spans, paths, product/vendor names. German statute/standard names stay German with an English gloss at first mention per file (e.g. "§ 5 UrhG (German Copyright Act)"). German quotation marks „…" → "…". References to CLAUDE.md sections use its English headings.
- Fixed headings/captions: `# 4. Verification` (05), `# 5. Appendices` (06), `## 3.12 Data acquisition and processing chain`, "Figure 1: Development phases", "Figure 2: Processing chain" (the SVGs' English titles).
- The repo's `site/` may be root-owned: always build from a scratch copy (recipe below).

## Scratch tooling

`S=/tmp/claude-1000/-home-snake-Dokumente-Projekte-01-normly-normly-app/dacb77f2-8983-4b32-b8a6-e7faa4c32931/scratchpad`. Shell state does not persist; start every command block with `S=<path>`. `$S/parity.py`, `$S/german_left.py` and `$S/docsvenv` exist; if missing, recreate them from Task 1 of `docs/superpowers/plans/2026-10-15-english-migration-mr1-foundation.md`.

Build recipe:
```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app && rm -rf $S/buildtree && mkdir -p $S/buildtree && git ls-files -co --exclude-standard -z | tar --null -cf - -T - | tar -x -C $S/buildtree && (cd $S/buildtree && $S/docsvenv/bin/zensical build > $S/build.log 2>&1); grep -c '^3 issues found' $S/build.log
```
Expected `1`. Note: while chapter 03 is translated but the README anchors are not yet rewritten (Tasks 4–8), the build may report more issues; that is expected until Task 9.

## File Structure

| Path | Change |
|---|---|
| `docs/glossary.md` | Task 2: SRS terms, split of the two criteria rows |
| `docs/srs/01-introduction.md`, `02-product-overview.md`, `05-verification.md`, `06-appendices.md` | Task 3: translated |
| `docs/srs/03-requirements.md` | Tasks 4–8: translated in five chunks |
| `docs/srs/README.md` | Task 9: translated; requirement anchors rewritten |
| `CLAUDE.md`, `docs/index.md` | Task 10: migration notes updated |

---

### Task 1: Chunk helper, originals and baseline

**Files:**
- Create (scratch, not committed): `$S/srs_chunk.py`

**Interfaces:**
- Produces: `srs_chunk.py FILE FIRST LAST` prints `03-requirements.md` from the heading `## 3.<FIRST> ` up to (not including) `## 3.<LAST+1> `; `FIRST=1` starts at line 1 (title and intro); `LAST=16` runs to the end. Used by Tasks 4–8.

- [ ] **Step 1: Write `$S/srs_chunk.py`**

```python
#!/usr/bin/env python3
"""Print one chunk of the SRS chapter 3. Usage: srs_chunk.py FILE FIRST LAST

FIRST=1 starts at line 1. The chunk ends before '## 3.<LAST+1> '.
"""
import re
import sys

path, first, last = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
out, on = [], first == 1
for line in open(path, encoding="utf-8"):
    m = re.match(r"## 3\.(\d+) ", line)
    if m:
        n = int(m.group(1))
        if n == first:
            on = True
        elif n > last:
            break
    if on:
        out.append(line)
sys.stdout.write("".join(out))
```

- [ ] **Step 2: Self-test**

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
for r in "1 4" "5 5" "6 9" "10 12" "13 16"; do python3 -I $S/srs_chunk.py docs/srs/03-requirements.md $r | wc -w; done
python3 -I $S/srs_chunk.py docs/srs/03-requirements.md 1 4 | head -1
python3 -I $S/srs_chunk.py docs/srs/03-requirements.md 13 16 | grep -c -E '^#{3,4} REQ-'
```
Expected: five counts summing to the file's ~9,890 words (≈1,950 / 1,770 / 2,040 / 1,980 / 2,140); first line `# 3. Anforderungen`; the last chunk contains the REQ-SEC, REQ-DRM, REQ-MOB and REQ-ACC requirements (16).

- [ ] **Step 3: Save originals and the baseline requirement ids**

```bash
mkdir -p $S/orig/srs && for f in README 01-introduction 02-product-overview 03-requirements 05-verification 06-appendices; do git show main:docs/srs/$f.md > $S/orig/srs/$f.md; done
<build recipe>
python3 -c "import re,sys; print('\n'.join(i for i in re.findall(r'<h[34] id=\"([^\"]+)\"', open(sys.argv[1],encoding='utf-8').read()) if i.startswith('req-')))" $S/buildtree/site/srs/03-requirements/index.html > $S/srs-ids-de.txt
wc -l $S/srs-ids-de.txt; head -2 $S/srs-ids-de.txt
```
Expected: build check `1`; 78 ids, first `req-ui-001-chat-oberflache-der-eigenstandigen-webanwendung`. If the built page path differs, find it with `ls $S/buildtree/site/srs/` and use it here and in Task 9.

- [ ] **Step 4: No commit (scratch only)**

---

### Task 2: SRS terms in the binding glossary

**Files:**
- Modify: `docs/glossary.md` (section "Terminology (binding)")

- [ ] **Step 1: Replace the combined criteria row**

The row whose German cell is "Akzeptanzkriterium, Abnahmekriterium" (English "acceptance criterion …") is replaced by two rows (owner decision 2026-10-16 — in the SRS they are two separate fields of every requirement):

| German | English |
|---|---|
| Akzeptanzkriterium (SRS field, a list) | Acceptance criteria |
| Abnahmekriterium (SRS field, a concrete acceptance test) | Acceptance test |

- [ ] **Step 2: Add rows (alphabetical by German term, existing format, skip duplicates)**

Owner decisions 2026-10-16:

| German | English |
|---|---|
| Neu gefasst durch (SRS status) | revised by |
| Normenanbieter (sellers of norms, e.g. DIN Media/Nautos) | norm vendor(s) |
| Quellenangabe, Quellenanzeige (in chat answers) | citation(s) (code: citations) |
| Quellenattribution (partner billing, REQ-PART-002) | source attribution |

Standard renderings (controller):

| German | English |
|---|---|
| Beitragsweg | contribution path |
| Datenlizenz | data license |
| Drittsoftware, Drittsysteme | third-party software, third-party systems |
| Expertensysteme | expert systems |
| Hauptzweig | main branch |
| Identitätsauflösung | identity resolution |
| Inhaltepartnerschaft | content partnership |
| Inhaltezulieferung | content supply |
| Kontopflicht | account requirement |
| Mandantenfähigkeit | multi-tenancy |
| Stand (date, as a label) | As of |
| Umsatzbeteiligung | revenue share |
| Vergütung | remuneration |
| Weitere Informationen (SRS field) | Further information |
| Wichtig (SRS label) | Important |
| Zusatzdienste | add-on services |

- [ ] **Step 3: Check**

```bash
git diff --stat; awk '/^## Terminology \(binding\)/{f=1} f' docs/glossary.md | grep -c '^| '
grep -n 'acceptance criterion' docs/glossary.md
```
Expected: only `docs/glossary.md` changed; row count +21 (1 removed, 2 + 20 added); the last grep prints nothing (or only prose that is updated to the two new terms — list it in the report).

- [ ] **Step 4: Commit**

```bash
git add docs/glossary.md
git commit -s -m "docs: add SRS terminology to the binding glossary

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Translate chapters 01, 02, 05, 06

**Files:**
- Modify: `docs/srs/01-introduction.md`, `docs/srs/02-product-overview.md`, `docs/srs/05-verification.md`, `docs/srs/06-appendices.md`

- [ ] **Step 1: Translate all four files using the translation brief below**

Translation brief (verbatim in every implementer prompt of Tasks 3–9):

> Translate the given German text of the normly SRS to English in place. Read `docs/glossary.md`, section "Terminology (binding)", first; its renderings are binding. Faithful translation only: do not add, drop, reword for style, or correct content; outdated statements stay. Keep Markdown structure, tables, lists, links, code spans, IDs, dates and numbers exactly; keep heading levels and numbering; keep the requirement block shape and the field labels from the plan's Global Constraints. Modal force must stay exact. `Normenausschuss` and `Trägerorganisation` stay German. German statute and standard names stay German with an English gloss at first mention in the file. Where an ADR or CLAUDE.md states the same rule in English, use the same wording for the same concept. Do NOT run git commands that change state. If any word or passage has no clear rendering under these rules, do not guess: leave a `[[QUESTION n]]` marker and list it in your report and final reply (German text, context, 1–3 candidates), finish the rest, and return NEEDS_CONTEXT.

File-specific: `02-product-overview.md` line "Figure 1: Entwicklungsphasen" → "Figure 1: Development phases". `01-introduction.md` contains "anerkannter Stand der Technik" → "recognized state of the art" (owner decision) and the definitions table (1.3) — every defined term follows the glossary.

- [ ] **Step 2: Resolve QUESTIONS with the owner; add answers to the glossary; remove markers** (`grep -n QUESTION docs/srs/0[1256]*.md` → empty)

- [ ] **Step 3: Checks**

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
for f in 01-introduction 02-product-overview 05-verification 06-appendices; do python3 -I $S/parity.py $S/orig/srs/$f.md docs/srs/$f.md; done
python3 -I $S/german_left.py docs/srs/01-introduction.md docs/srs/02-product-overview.md docs/srs/05-verification.md docs/srs/06-appendices.md
git diff --stat
```
Expected: four times `PARITY OK`; no suspect lines except justified quoted German (listed in the report); only these four files changed.

- [ ] **Step 4: Commit**

```bash
git add docs/srs/01-introduction.md docs/srs/02-product-overview.md docs/srs/05-verification.md docs/srs/06-appendices.md
git commit -s -m "docs: translate SRS chapters 1, 2, 4 and 5 to English

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tasks 4–8: Translate chapter 3 (requirements) in five chunks

Each chunk task follows the same steps; only the range differs. The translator edits `docs/srs/03-requirements.md` in place, only inside its range.

| Task | Range (`srs_chunk.py` args) | Content | Notes |
|---|---|---|---|
| 4 | `1 4` | Title, intro, 3.1 External interfaces, 3.2, 3.3, 3.4 | REQ-UI, REQ-INT, REQ-FUNC, REQ-PERF, compliance; REQ-UI-003 citations (Quellenanzeige → citation) |
| 5 | `5 5` | 3.5 Design and implementation | REQ-INST, REQ-BUILD, REQ-DIST (Auslieferung → shipping; REQ-DIST-004 title) |
| 6 | `6 9` | 3.6 AI/ML – 3.9 Reference graph | REQ-OSS, REQ-GIT (REQ-GIT-002 "Neu gefasst durch" → revised by), REQ-GRAPH |
| 7 | `10 12` | 3.10 – 3.12 | REQ-PART (source attribution, revenue share), REQ-COM, REQ-PIPE; heading 3.12 fixed; "Figure 2: Verarbeitungskette" → "Figure 2: Processing chain"; "zieht … zurück" per the glossary's withdrawal/retired/withdrawn rule |
| 8 | `13 16` | 3.13 – 3.16 | REQ-SEC, REQ-DRM (Kennzeichnung → marking; no file handed out), REQ-MOB, REQ-ACC (exhaustive account-feature list — must match CLAUDE.md/ADR-017 scope) |

**Files:**
- Modify: `docs/srs/03-requirements.md` (only the chunk's range)

**Interfaces:**
- Consumes: `$S/srs_chunk.py`, `$S/parity.py`, `$S/german_left.py`, `$S/orig/srs/03-requirements.md`, the glossary from Task 2.
- Produces: the translated range. Requirement headings keep their level and the shape `REQ-XXX-NNN — ` so Task 9 can map anchors by ID.

- [ ] **Step 1: Translate the range** using the translation brief from Task 3.

- [ ] **Step 2: Resolve QUESTIONS with the owner; add each answer to the glossary; remove the markers** (`grep -n QUESTION docs/srs/03-requirements.md` → empty)

- [ ] **Step 3: Checks for the range**

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
python3 -I $S/srs_chunk.py $S/orig/srs/03-requirements.md <FIRST> <LAST> > $S/chunk-de.md
python3 -I $S/srs_chunk.py docs/srs/03-requirements.md <FIRST> <LAST> > $S/chunk-en.md
python3 -I $S/parity.py $S/chunk-de.md $S/chunk-en.md
python3 -I $S/german_left.py $S/chunk-en.md
git diff --stat
```
Expected: `PARITY OK`; no suspect lines except justified quoted German (listed); only `docs/srs/03-requirements.md` changed, and only inside the range (verify that the text before and after the range is byte-identical to HEAD, e.g. via sha256 of the outside parts).

- [ ] **Step 4: Commit**

```bash
git add docs/srs/03-requirements.md
git commit -s -m "docs: translate SRS sections 3.<FIRST>–3.<LAST> to English

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
(Task 4: "translate SRS chapter 3 intro and sections 3.1–3.4"; Task 5: "translate SRS section 3.5".)

---

### Task 9: Translate the SRS index and rewrite requirement anchors

**Files:**
- Modify: `docs/srs/README.md`

- [ ] **Step 1: Translate `docs/srs/README.md`** using the translation brief. The requirement titles in its index tables must be byte-identical to the English requirement headings in `03-requirements.md` (copy them from there, do not re-translate). Chapter/section titles must match the translated headings of 01–06. Link targets stay as they are in this step.

- [ ] **Step 2: Build and map the anchors by requirement ID**

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
<build recipe>
python3 -c "import re,sys; print('\n'.join(i for i in re.findall(r'<h[34] id=\"([^\"]+)\"', open(sys.argv[1],encoding='utf-8').read()) if i.startswith('req-')))" $S/buildtree/site/srs/03-requirements/index.html > $S/srs-ids-en.txt
python3 -I - $S/srs-ids-de.txt $S/srs-ids-en.txt > $S/srs-id-map.txt <<'EOF'
import re, sys
key = lambda i: re.match(r"req-[a-z]+-\d+[a-z]?", i).group(0)
de = {key(l.strip()): l.strip() for l in open(sys.argv[1]) if l.strip()}
en = {key(l.strip()): l.strip() for l in open(sys.argv[2]) if l.strip()}
assert de.keys() == en.keys(), (sorted(de.keys() ^ en.keys()))
for k in sorted(de):
    print(de[k], en[k])
EOF
wc -l $S/srs-id-map.txt
```
Expected: 78 lines; the assertion holds (same set of requirement IDs).

- [ ] **Step 3: Rewrite anchors in every tracked file**

```bash
files=$(git grep -l '03-requirements\.md#req-')
python3 -I - $S/srs-id-map.txt $files <<'EOF'
import sys
pairs = [l.split() for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
for path in sys.argv[2:]:
    s = open(path, encoding="utf-8").read()
    t = s
    for old, new in pairs:
        for end in (")", "`", "\n", " "):
            t = t.replace("03-requirements.md#" + old + end, "03-requirements.md#" + new + end)
    if t != s:
        open(path, "w", encoding="utf-8").write(t)
        print("updated", path)
EOF
git grep -n -o -E '03-requirements\.md#req-[a-z0-9-]+' | sed 's/.*#//' | sort -u > $S/srs-used.txt
grep -v -x -F -f $S/srs-ids-en.txt $S/srs-used.txt
```
Expected: `docs/srs/README.md` updated (and any other file that linked a requirement); the final grep prints nothing except the prose prefix `req-` in older plans (list any hit in the report).

- [ ] **Step 4: Checks and commit**

```bash
python3 -I $S/parity.py $S/orig/srs/README.md docs/srs/README.md
python3 -I $S/german_left.py docs/srs/README.md
<build recipe>
git add -A
git commit -s -m "docs: translate the SRS index and point requirement links to English anchors

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
Expected before commit: `PARITY OK`; no suspect lines; build check `1`.

---

### Task 10: Update the migration pointers

**Files:**
- Modify: `CLAUDE.md` (Language section), `docs/index.md`

- [ ] **Step 1: `CLAUDE.md`** — in the paragraph "Migration in progress (2026-10-15): `docs/srs/` and `docs/superpowers/` are still being translated, …", remove `docs/srs/` so only `docs/superpowers/` remains (fix the grammar: "`docs/superpowers/` is still being translated, … Until then it remains German; new text in it is written in English."). Change nothing else. Use the Edit tool.

- [ ] **Step 2: `docs/index.md`** — delete the paragraph
```
The Requirements (SRS) are currently German-only; the rest of the site
is in English, and their translation is tracked separately.
```
including its trailing blank line, so the surrounding sections join cleanly.

- [ ] **Step 3: Check and commit**

```bash
S=<path>; python3 -I $S/german_left.py CLAUDE.md docs/index.md; git diff --stat
git add CLAUDE.md docs/index.md
git commit -s -m "docs: mark the SRS as translated in the migration notes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Final verification and review

- [ ] **Step 1: Invoke `superpowers:verification-before-completion` and run fresh**

```bash
S=<path>; cd /home/snake/Dokumente/Projekte/01_normly/normly-app
git status --short
for f in README 01-introduction 02-product-overview 03-requirements 05-verification 06-appendices; do printf '%s: ' $f; python3 -I $S/parity.py $S/orig/srs/$f.md docs/srs/$f.md | tail -1; done
python3 -I $S/german_left.py docs/srs/*.md
grep -c -E '^#{3,4} REQ-' docs/srs/03-requirements.md        # 78
grep -c '[„“]' docs/srs/*.md                              # 0 per file
<build recipe>                                             # 1
```

- [ ] **Step 2: Whole-branch review** on the most capable model: meaning drift (especially REQ-PIPE, REQ-SEC, REQ-DRM, REQ-ACC, REQ-OSS, REQ-GIT), terminology consistency with the glossary, the ADRs and CLAUDE.md, index titles identical to headings, anchor integrity. One fix wave, one scoped re-review.

- [ ] **Step 3: Hand over to the owner** — results, open questions, ask before pushing and opening the PR. After merge: write the MR 4 plan (`docs/superpowers/`).
