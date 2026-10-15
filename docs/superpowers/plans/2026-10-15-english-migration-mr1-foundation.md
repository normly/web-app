# English migration, MR 1 (foundation) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the foundation of the English migration: binding glossary, English root files and `CLAUDE.md`, English diagrams, English file names with all links fixed, and the leftover German loanword removed from the already-English public docs.

**Architecture:** Spec `docs/superpowers/specs/2026-10-15-english-docs-migration-design.md` (approved 2026-10-15). This plan covers only its MR 1. MR 2 (ADRs), MR 3 (SRS) and MR 4 (`docs/superpowers/`) get their own plans, written after MR 1 merges so they inherit the final glossary. Translation is faithful: no content changes. Mechanical parity checks compare every translated file with its original.

**Tech Stack:** Markdown, SVG, Zensical docs build (`zensical.toml`), Python 3 for throwaway check scripts, Chromium (headless) for SVG rendering.

## Global Constraints

- Work on branch `docs/english-migration` (already contains the two spec commits). Nothing is pushed and no merge request is opened without the owner's explicit confirmation (billed pipeline runs).
- Only the main session commits. Subagents translate and report; they never run `git commit`. Every commit: `git commit -s` plus the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never run `git config`.
- Commits use Conventional Commits, English, e.g. `docs: translate GOVERNANCE.md to English`.
- Binding terminology (spec): Norm→norm, Regelwerk→standards, "Normen und Regelwerke"→"norms and standards", Herausgeber→publisher, Referenzgraph→reference graph, Wissensbasis/Wissensbestand→knowledge base, Rechteklassifikation→rights classification, Rechtsraum→jurisdiction, Ausgabestand→edition, Quelllieferung→source delivery, Abstammung→lineage, Herkunft (attribute)→provenance, Rücknahme→withdrawal, Rollback (deployment)→rollback, Sicherung→backup, Tombstone→tombstone, Verarbeitungskette→processing chain, Beitragsfassade→contribution facade, Nachtrag→addendum, Akzeptanzkriterium/Abnahmekriterium→acceptance criterion, Konto-/Kontolöschung→account deletion. `Normenausschuss` and `Trägerorganisation` stay German. Compounds follow their stem.
- A word or passage with no clear rendering under this terminology: stop and ask the owner. Do not decide.
- Unchanged: code identifiers, `REQ-…`/`ADR-…` IDs, product names (*normly*, *Normtracker*, *Perinorm*), German statute/standard names (add an English gloss in parentheses at first mention per document, e.g. "§ 5 UrhG (German Copyright Act)"), quoted German UI strings.
- Anchors inside `docs/adr/README.md` and `docs/srs/03-…` do not change in this MR (headings stay German until MR 2/3). Only file names change here.
- `docs/superpowers/` is not touched in this MR, except this plan and the spec. Mentions of old file names inside historical specs and plans are fixed in MR 4. Exception: if the docs build reports a *new* broken link caused by a rename, fix that one reference.
- Files in the owner's repo are licensed AGPL-3.0; these are Markdown/SVG files without source headers, so none are added.

## Scratch tooling

All scratch files live in `$SCRATCH=/tmp/claude-1000/-home-snake-Dokumente-Projekte-01-normly-normly-app/dacb77f2-8983-4b32-b8a6-e7faa4c32931/scratchpad`. They are not committed. MR 2–4 plans recreate them from Task 1. Shell state does not persist between commands, so every command block that uses `$S` must start with `S=<the path above>`.

## File Structure

| Path | Change |
|---|---|
| `docs/glossary.md` | modify: add binding terminology entries |
| `GOVERNANCE.md`, `TRADEMARK.md`, `MAINTAINERS.md` | translate |
| `CLAUDE.md` | translate; rewrite "Sprache" section as "Language" |
| `docs/normly_Entwicklungsphasen.svg` → `docs/normly_development-phases.svg` | rename + translate labels |
| `docs/normly_Verarbeitungskette.svg` → `docs/normly_processing-chain.svg` | rename + translate labels |
| `docs/srs/01-einfuehrung.md` → `01-introduction.md`, `02-produktueberblick.md` → `02-product-overview.md`, `03-anforderungen.md` → `03-requirements.md`, `05-verifikation.md` → `05-verification.md`, `06-anhaenge.md` → `06-appendices.md` | rename only |
| `docs/concepts/lizenzmodell.md` → `license-model.md`, `docs/concepts/normen-graph.md` → `norm-graph.md` | rename only |
| `zensical.toml`, `docs/index.md`, `docs/glossary.md`, `README.md`, `docs/srs/README.md`, `docs/adr/README.md` | link updates for renames |
| `README.md`, `CONTRIBUTING.md` | replace leftover "Regelwerk(e)" |

Note: `normen-graph.md` was not in the spec's rename table. It is a German file name, so it is renamed here; `norm-graph.md` follows the Norm→norm mapping.

---

### Task 1: Check scripts and docs-build baseline

**Files:**
- Create (scratch, not committed): `$SCRATCH/parity.py`, `$SCRATCH/german_left.py`

**Interfaces:**
- Produces: `parity.py ORIGINAL NEW [OLD=NEW ...]` exits 0 if structure matches; `german_left.py FILE...` prints suspect lines (exit 0 always, human reviews). Later tasks call both.

- [ ] **Step 1: Write `parity.py`**

```python
#!/usr/bin/env python3
"""Structure parity between an original file and its translation.

Usage: parity.py ORIGINAL NEW [OLD=NEW ...]
OLD=NEW pairs map renamed link targets in ORIGINAL before comparing.
Compared: headings, table rows, list items, code fences, REQ-/ADR- IDs,
link target paths (anchors ignored, because headings get translated).
"""
import re
import sys


def metrics(text, mapping):
    lines, fence, kept = text.splitlines(), False, []
    fences = 0
    for line in lines:
        if line.lstrip().startswith("```"):
            fence = not fence
            fences += 1
            continue
        if not fence:
            kept.append(line)
    m = {
        "headings": sum(1 for l in kept if re.match(r"#{1,6} ", l)),
        "table_rows": sum(1 for l in kept if l.lstrip().startswith("|")),
        "list_items": sum(1 for l in kept if re.match(r"\s*([-*]|\d+\.) ", l)),
        "code_fences": fences,
    }
    ids = set(re.findall(r"\b(?:REQ-[A-Z]+-\d+[A-Z]?|ADR-\d+)\b", text))
    targets = set()
    for t in re.findall(r"\]\(([^)\s]+)", text):
        for old, new in mapping.items():
            t = t.replace(old, new)
        targets.add(t.split("#")[0])
    return m, ids, targets


def main():
    orig, new = sys.argv[1], sys.argv[2]
    mapping = dict(a.split("=", 1) for a in sys.argv[3:])
    mo, io, to = metrics(open(orig, encoding="utf-8").read(), mapping)
    mn, i_n, tn = metrics(open(new, encoding="utf-8").read(), {})
    ok = True
    for k in mo:
        if mo[k] != mn[k]:
            ok = False
            print(f"MISMATCH {k}: original {mo[k]} vs new {mn[k]}")
    for label, a, b in (("IDs", io, i_n), ("link targets", to, tn)):
        if a != b:
            ok = False
            print(f"MISMATCH {label}: only original {sorted(a - b)}; only new {sorted(b - a)}")
    print("PARITY OK" if ok else "PARITY FAILED")
    sys.exit(0 if ok else 1)


main()
```

- [ ] **Step 2: Write `german_left.py`**

```python
#!/usr/bin/env python3
"""Print lines that still look German. Usage: german_left.py FILE..."""
import re
import sys

ALLOWED = ["Normenausschuss", "Normenausschüsse", "Trägerorganisation"]
MARKERS = re.compile(
    r"\b(der|die|das|und|nicht|ist|wird|werden|für|mit|von|zu|auf|dass|oder|"
    r"bei|eine|einer|ein|sind|auch|nur|wenn|aus|nach)\b",
    re.IGNORECASE,
)
UMLAUT = re.compile(r"[äöüÄÖÜß]")

for path in sys.argv[1:]:
    fence = False
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        s = re.sub(r"`[^`]*`", "", line)
        for w in ALLOWED:
            s = s.replace(w, "")
        if UMLAUT.search(s) or len(MARKERS.findall(s)) >= 2:
            print(f"{path}:{n}: {line.rstrip()[:150]}")
```

- [ ] **Step 3: Self-test both scripts**

Run:
```bash
cd /home/snake/Dokumente/Projekte/01_normly/normly-app
S=/tmp/claude-1000/-home-snake-Dokumente-Projekte-01-normly-normly-app/dacb77f2-8983-4b32-b8a6-e7faa4c32931/scratchpad
python3 -I $S/parity.py README.md README.md && python3 -I $S/german_left.py README.md GOVERNANCE.md | head -5
```
Expected: `PARITY OK`; `german_left.py` prints no line for `README.md` and several for `GOVERNANCE.md`.

- [ ] **Step 4: Build the docs locally and record the baseline**

Run:
```bash
cd /home/snake/Dokumente/Projekte/01_normly/normly-app
S=/tmp/claude-1000/-home-snake-Dokumente-Projekte-01-normly-normly-app/dacb77f2-8983-4b32-b8a6-e7faa4c32931/scratchpad
uv venv $S/docsvenv && uv pip install --python $S/docsvenv/bin/python "zensical==0.0.60" "mkdocstrings==1.0.6" "mkdocstrings-python==2.0.8" "griffelib==2.3.0" "pymdown-extensions==12.1"
$S/docsvenv/bin/zensical build 2>&1 | tee $S/build-baseline.log | tail -5
```
Expected: the log ends with `3 issues found` (the CI guard, `.github/workflows/ci.yml`). If the count differs on an unchanged tree, stop and report; the baseline in CI would be wrong too. `site/` is git-ignored.

- [ ] **Step 5: No commit (scratch files only)**

---

### Task 2: Glossary entries

**Files:**
- Modify: `docs/glossary.md`

**Interfaces:**
- Produces: the public, binding definitions that Tasks 4–7 and MR 2–4 refer to.

- [ ] **Step 1: Append the entries to `docs/glossary.md`**

Add after the existing `**Category A–D**` entry, same definition-list style:

```markdown
**Norm**
: A document issued by a standardization body (German *Norm*), for
  example DIN EN ISO 9001. In this repository "norm" always means this,
  never a social convention.

**Standards**
: The collective term for all rule sets normly covers (German
  *Regelwerk*, plural *Regelwerke*): norms, but also legal texts and
  rules from bodies such as DGUV or BAuA. "Norm" and "standard" are
  separate terms here: a norm is one kind of standard.

**Lineage**
: The chain of derivation from a source delivery to every artifact
  built from it (section, segment, embedding, graph edge, export file).
  Makes withdrawal possible. Not the same as provenance.

**Provenance**
: Where a piece of content comes from (publisher, retrieval path, legal
  basis, jurisdiction, check date). An attribute of a record, kept in
  the source register.

**Source delivery**
: One batch of content received from a source, the unit that lineage
  refers back to and that can be withdrawn as a whole.

**Withdrawal**
: Removing a source delivery and everything derived from it, for example
  at the end of a contract or after a takedown request. Distinct from
  a deployment *rollback*.

**Edition**
: The issue state of a Work (German *Ausgabestand*); part of its
  identifier together with publisher, number and part number.

**Processing chain**
: The single pipeline from source to delivery that all content passes
  through, regardless of provenance (German *Verarbeitungskette*).

**Contribution facade**
: Historical term from ADR-004: a public GitHub presence for issues and
  pull requests in front of a primary code platform elsewhere.
  Superseded by ADR-021.
```

- [ ] **Step 2: Check**

Run:
```bash
cd /home/snake/Dokumente/Projekte/01_normly/normly-app
python3 -I $S/german_left.py docs/glossary.md; git diff --stat
```
Expected: no suspect lines; only `docs/glossary.md` changed. (Set `S` as in Task 1.)

- [ ] **Step 3: Commit**

```bash
git add docs/glossary.md
git commit -s -m "docs: add binding terminology entries to the glossary

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Rename German file names and fix links

**Files:**
- Rename: see File Structure table (7 Markdown files, 2 SVGs)
- Modify: every tracked file outside `docs/superpowers/` that references an old name

**Interfaces:**
- Consumes: baseline from Task 1.
- Produces: the new file names used by every later task and MR.

- [ ] **Step 1: Rename with `git mv`**

```bash
cd /home/snake/Dokumente/Projekte/01_normly/normly-app
git mv docs/srs/01-einfuehrung.md docs/srs/01-introduction.md
git mv docs/srs/02-produktueberblick.md docs/srs/02-product-overview.md
git mv docs/srs/03-anforderungen.md docs/srs/03-requirements.md
git mv docs/srs/05-verifikation.md docs/srs/05-verification.md
git mv docs/srs/06-anhaenge.md docs/srs/06-appendices.md
git mv docs/concepts/lizenzmodell.md docs/concepts/license-model.md
git mv docs/concepts/normen-graph.md docs/concepts/norm-graph.md
git mv docs/normly_Entwicklungsphasen.svg docs/normly_development-phases.svg
git mv docs/normly_Verarbeitungskette.svg docs/normly_processing-chain.svg
```

- [ ] **Step 2: Rewrite references (exact file-name tokens only)**

The pattern deliberately requires the `.md`/`.svg` suffix so ADR anchors such as `#adr-002-lizenzmodell-…` and prose such as "Verarbeitungskette" stay untouched.

```bash
files=$(git grep -l -E '(01-einfuehrung|02-produktueberblick|03-anforderungen|05-verifikation|06-anhaenge)\.md|lizenzmodell\.md|normen-graph\.md|normly_(Entwicklungsphasen|Verarbeitungskette)\.svg' -- . ':!docs/superpowers')
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
  $files
```
Expected file list: `README.md`, `docs/adr/README.md`, `docs/glossary.md`, `docs/index.md`, `docs/concepts/license-model.md`, `docs/concepts/norm-graph.md`, `docs/srs/README.md`, `zensical.toml`.

- [ ] **Step 3: Verify no old names remain outside `docs/superpowers/`**

```bash
git grep -n -E '01-einfuehrung|02-produktueberblick|03-anforderungen|05-verifikation|06-anhaenge|lizenzmodell\.md|normen-graph|normly_(Entwicklungsphasen|Verarbeitungskette)' -- . ':!docs/superpowers'
```
Expected: empty output.

- [ ] **Step 4: Build and compare with the baseline**

```bash
$S/docsvenv/bin/zensical build 2>&1 | tee $S/build-after-rename.log | tail -5; grep -c '^3 issues found' $S/build-after-rename.log
```
Expected: `3 issues found` (grep prints `1`). If more issues appear, read them with `grep -i -B2 -A2 -E 'warn|error' $S/build-after-rename.log`. A new broken link into a renamed file from `docs/superpowers/` is fixed individually (Global Constraints exception); any other cause: stop and report.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -s -m "docs: rename German file names to English and fix links

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git show --stat --format= HEAD | tail -15
```
Expected: renames recorded as renames (`=>`), nothing outside the file list changed.

---

### Task 4: Translate GOVERNANCE.md and MAINTAINERS.md

**Files:**
- Modify: `GOVERNANCE.md`, `MAINTAINERS.md`

**Interfaces:**
- Consumes: glossary, `parity.py`, `german_left.py`.

- [ ] **Step 1: Save the originals for comparison**

```bash
cd /home/snake/Dokumente/Projekte/01_normly/normly-app
mkdir -p $S/orig && git show HEAD:GOVERNANCE.md > $S/orig/GOVERNANCE.md && git show HEAD:MAINTAINERS.md > $S/orig/MAINTAINERS.md
```

- [ ] **Step 2: Translate (subagent or inline) using the translation brief below**

Translation brief (use verbatim in any subagent prompt):

> Translate the file from German to English in place. Faithful translation only: do not add, drop, reword for style, or correct content; keep Markdown structure, tables, links, code, IDs and numbers exactly. Terminology is binding: Norm→norm, Regelwerk→standards, "Normen und Regelwerke"→"norms and standards", Herausgeber→publisher, Referenzgraph→reference graph, Wissensbasis→knowledge base, Rechteklassifikation→rights classification, Rechtsraum→jurisdiction, Ausgabestand→edition, Quelllieferung→source delivery, Abstammung→lineage, Herkunft→provenance, Rücknahme→withdrawal, Sicherung→backup, Verarbeitungskette→processing chain, Nachtrag→addendum. `Normenausschuss` and `Trägerorganisation` stay German. German statute and standard names stay German with an English gloss in parentheses at first mention. Do NOT run git commands. If any word or passage has no clear rendering under these rules, do not guess: list it in your final report under "QUESTIONS" with the German text and your candidate renderings, and leave a `[[QUESTION n]]` marker in the file.

Placeholder cells in `MAINTAINERS.md` such as `*(zu ergänzen)*` become `*(to be added)*`. The row label "Verarbeitungskette und Quellen" becomes "Processing chain and sources".

- [ ] **Step 3: Resolve any QUESTIONS with the owner, then remove all `[[QUESTION n]]` markers**

Run: `grep -n 'QUESTION' GOVERNANCE.md MAINTAINERS.md` — Expected: no output.

- [ ] **Step 4: Run the checks**

```bash
python3 -I $S/parity.py $S/orig/GOVERNANCE.md GOVERNANCE.md
python3 -I $S/parity.py $S/orig/MAINTAINERS.md MAINTAINERS.md
python3 -I $S/german_left.py GOVERNANCE.md MAINTAINERS.md
```
Expected: `PARITY OK` twice; no suspect lines (a quoted German name flagged by the heuristic is checked by eye).

- [ ] **Step 5: Read both files once end to end for meaning, then commit**

```bash
git add GOVERNANCE.md MAINTAINERS.md
git commit -s -m "docs: translate GOVERNANCE.md and MAINTAINERS.md to English

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Translate TRADEMARK.md

Separate from Task 4 because the text is legal and a reviewer should be able to reject it on its own.

**Files:**
- Modify: `TRADEMARK.md`

- [ ] **Step 1: Save the original**

```bash
git show HEAD:TRADEMARK.md > $S/orig/TRADEMARK.md
```

- [ ] **Step 2: Translate using the translation brief from Task 4**

Extra rule: legal terms of art (e.g. *Wort-/Bildmarke*, *Nutzungsberechtigung*, statute references such as MarkenG) are not translated by guess. Every such term goes to QUESTIONS with candidates unless it is an unambiguous standard rendering (word mark, logo mark). The owner decides.

- [ ] **Step 3: Resolve QUESTIONS, remove markers**

Run: `grep -n 'QUESTION' TRADEMARK.md` — Expected: no output.

- [ ] **Step 4: Run the checks**

```bash
python3 -I $S/parity.py $S/orig/TRADEMARK.md TRADEMARK.md
python3 -I $S/german_left.py TRADEMARK.md
```
Expected: `PARITY OK`; no suspect lines.

- [ ] **Step 5: Commit**

```bash
git add TRADEMARK.md
git commit -s -m "docs: translate TRADEMARK.md to English

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Translate the two diagrams

**Files:**
- Modify: `docs/normly_development-phases.svg`, `docs/normly_processing-chain.svg`

**Interfaces:**
- Consumes: glossary, binding terminology.
- Produces: English diagrams referenced from `README.md` and `docs/srs/README.md`.

- [ ] **Step 1: Check that all text sits in plain `<text>` elements and read the canvas size**

```bash
cd /home/snake/Dokumente/Projekte/01_normly/normly-app
grep -c '<tspan' docs/normly_*.svg; grep -o 'viewBox="[^"]*"' docs/normly_*.svg
```
Expected: `0` for both files, plus two viewBox values. If any `<tspan>` exists, extend Step 3's script to handle it before continuing.

- [ ] **Step 2: Render the "before" images**

```bash
for f in development-phases processing-chain; do
  chromium --headless --disable-gpu --no-sandbox --hide-scrollbars --window-size=1400,1000 --screenshot=$S/before-$f.png "file://$PWD/docs/normly_$f.svg" 2>/dev/null
done
ls -la $S/before-*.png
```
(Adjust `--window-size` to the viewBox width/height from Step 1.) Open both PNGs with the Read tool to see the layout.

- [ ] **Step 3: Extract the strings, translate, apply**

Extraction script (`$S/svg_extract.py`):

```python
import json, re, sys
out = {}
for p in sys.argv[1:]:
    for m in re.finditer(r"<text[^>]*>([^<]*)</text>", open(p, encoding="utf-8").read()):
        out[m.group(1)] = ""
json.dump(out, open(sys.argv[0].replace("svg_extract.py", "svg_strings.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "unique strings")
```

Run: `python3 -I $S/svg_extract.py docs/normly_development-phases.svg docs/normly_processing-chain.svg`

Fill in `$S/svg_strings.json` (value = English text per German key) following the translation brief. XML entities (`&amp;`, `&lt;`) stay as they are. Strings that are only IDs, numbers or symbols map to themselves. Unclear strings go to the owner as QUESTIONS before applying.

Apply script (`$S/svg_apply.py`); it aborts if any string is untranslated:

```python
import json, re, sys
tr = json.load(open(sys.argv[1], encoding="utf-8"))
for p in sys.argv[2:]:
    s = open(p, encoding="utf-8").read()
    def sub(m):
        t = tr[m.group(2)]
        if not t:
            sys.exit(f"untranslated: {m.group(2)!r}")
        return m.group(1) + t + m.group(3)
    s = re.sub(r"(<text[^>]*>)([^<]*)(</text>)", sub, s)
    open(p, "w", encoding="utf-8").write(s)
```

Run: `python3 -I $S/svg_apply.py $S/svg_strings.json docs/normly_development-phases.svg docs/normly_processing-chain.svg`

- [ ] **Step 4: Render the "after" images and check for overflow**

Same chromium command with `after-` file names. Open both PNGs with the Read tool and compare with the "before" images: no text may run outside its box or overlap neighbours. English is usually shorter than German, but check. If a label overflows, shorten the wording (still faithful) or reduce `font-size` on that single element; ask the owner if the choice changes meaning.

- [ ] **Step 5: German-leftover check**

```bash
grep -o '<text[^>]*>[^<]*' docs/normly_*.svg | sed 's/<text[^>]*>//' > $S/svg-text.txt
python3 -I $S/german_left.py $S/svg-text.txt
grep -c -E '[äöüÄÖÜß]' $S/svg-text.txt
```
Expected: no suspect lines; the count is `0`.

- [ ] **Step 6: Commit**

```bash
git add docs/normly_development-phases.svg docs/normly_processing-chain.svg
git commit -s -m "docs: translate diagram labels to English

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Remove leftover "Regelwerk" from README and CONTRIBUTING

**Files:**
- Modify: `README.md:5,7,16`, `CONTRIBUTING.md:7,120`

- [ ] **Step 1: Apply the five replacements**

| File:line | Old | New |
|---|---|---|
| `README.md:5` | `knowledge about standards and Regelwerke` | `knowledge about norms and standards` |
| `README.md:7` | `which Regelwerke reference each other` | `which standards reference each other` |
| `README.md:16` | `Regelwerke are` | `Standards are` |
| `CONTRIBUTING.md:7` | `between Regelwerke,` | `between standards,` |
| `CONTRIBUTING.md:120` | `which Regelwerk, which publisher` | `which standard, which publisher` |

Use the Edit tool for each; the line 5 change follows the spec mapping "Normen und Regelwerke → norms and standards" (the README tagline already says "norms and standards"). Existing uses of "standard(s)" elsewhere stay (owner decision, 2026-10-15).

- [ ] **Step 2: Check**

```bash
git grep -n -i 'Regelwerk' -- README.md CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md frontend/README.md docs/index.md docs/glossary.md docs/concepts docs/guide docs/reference
git diff --stat
```
Expected: the first command prints only the new glossary lines that mention *Regelwerk* as the German source word; the diff touches only `README.md` and `CONTRIBUTING.md`, 3 and 2 lines.

- [ ] **Step 3: Commit**

```bash
git add README.md CONTRIBUTING.md
git commit -s -m "docs: replace leftover German loanword Regelwerk

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Translate CLAUDE.md and rewrite its language section

Done last because it records the new policy and refers to the glossary and spec created above.

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Save the original**

```bash
git show HEAD:CLAUDE.md > $S/orig/CLAUDE.md
```

- [ ] **Step 2: Translate the whole file using the translation brief from Task 4**

Everything is translated faithfully (rules, tables, ADR and REQ references, the arrows `→`), including the section headings (`Nicht verhandelbar` → `Non-negotiable`, `Bei jeder Codeänderung` → `For every code change`, `Arbeitsweise: Wann abstimmen, wann direkt umsetzen` → `Working mode: when to align first, when to implement directly`, `Architekturregeln` → `Architecture rules`, `Neue Datenquellen` → `New data sources`, `Technischer Rahmen` → `Technical framework`, `Identifikatoren` → `Identifiers`, `Weitere Repository-Dateien` → `Other repository files`, `Wenn etwas unklar ist` → `When something is unclear`). Skill names (`brainstorming`, `systematic-debugging`, `verification-before-completion`) stay as they are. The line "Diese Datei … Auto-Mode …" keeps its meaning exactly. Skip the "Sprache" section; Step 3 replaces it.

- [ ] **Step 3: Replace the "Sprache" section with the following text under the heading `## Language`**

```markdown
## Language

Everything in this repository is in English: code, identifiers, commits,
documentation (`docs/`, code reference, guides), ADRs, the SRS, specs and
plans under `docs/superpowers/`, root files, and this file. International
reach takes priority. Terms from the standards domain keep their German
form where there is no established English equivalent (e.g.
`Normenausschuss`, `Trägerorganisation`), regardless of the language of
the surrounding text. The app's own language switch (German/English for
end users) is unaffected. → ADR-020

Terminology is binding and defined in `docs/glossary.md`: *Norm* is
"norm", *Regelwerk* is "standards" (the broader term, which includes
norms); "norms and standards" names both together.

Migration in progress (2026-10-15): `docs/adr/`, `docs/srs/` and
`docs/superpowers/` are still being translated, see
`docs/superpowers/specs/2026-10-15-english-docs-migration-design.md`. Until
then they remain German; new text in them is written in English.
```

- [ ] **Step 4: Check**

```bash
python3 -I $S/parity.py $S/orig/CLAUDE.md CLAUDE.md
python3 -I $S/german_left.py CLAUDE.md
grep -n 'QUESTION' CLAUDE.md
```
Expected: `PARITY OK`. The old "Sprache" section and the new "Language" section both have one heading, no list items, no tables, no code fences, no IDs except `ADR-020`, and no links, so the metrics must match exactly. Any mismatch is a defect: fix it. `german_left.py` prints nothing; `grep` prints nothing.

- [ ] **Step 5: Read the translated file end to end against the original once**

Compare each rule in the "Non-negotiable" and "Architecture rules" sections one by one with `$S/orig/CLAUDE.md`. Meaning must be identical. These rules are legal and strategic (CLAUDE.md says so itself).

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -s -m "docs: translate CLAUDE.md to English and make English the repo-wide language

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Audit non-Markdown files for stray German (report only)

**Files:** none changed.

- [ ] **Step 1: Scan tracked non-Markdown text files**

```bash
cd /home/snake/Dokumente/Projekte/01_normly/normly-app
git ls-files | grep -v -E '\.(md|svg|png|jpg|ico|woff2?|lock)$' | grep -v -E '^docs/superpowers/' | grep -v -E 'locale|i18n|/de[./]|fixtures?/|\.snap$' > $S/audit-files.txt
wc -l $S/audit-files.txt
xargs -a $S/audit-files.txt python3 -I $S/german_left.py 2>/dev/null | cut -c1-170 | head -80
```
Expected: a (possibly empty) list of suspect lines in comments, configs and scripts.

- [ ] **Step 2: Report to the owner**

Summarise per file how many lines and what kind (comment, string literal, config key). **Do not change anything.** The owner decides what to translate, in this MR or a later one. Note that quoted UI strings and test data in German are expected and not findings.

---

### Task 10: Final verification and review

- [ ] **Step 1: Invoke `superpowers:verification-before-completion` and run every check fresh**

```bash
cd /home/snake/Dokumente/Projekte/01_normly/normly-app
git status --short                       # expected: clean
git log --oneline main..HEAD             # expected: 2 spec commits + 2 plan commits + 7 task commits (Tasks 2-8)
git grep -n -E '01-einfuehrung|02-produktueberblick|03-anforderungen|05-verifikation|06-anhaenge|lizenzmodell\.md|normen-graph|normly_(Entwicklungsphasen|Verarbeitungskette)' -- . ':!docs/superpowers'   # expected: empty
python3 -I $S/german_left.py CLAUDE.md GOVERNANCE.md TRADEMARK.md MAINTAINERS.md docs/glossary.md   # expected: empty
$S/docsvenv/bin/zensical build 2>&1 | tee $S/build-final.log | tail -3; grep -c '^3 issues found' $S/build-final.log   # expected: 1
```
Report each result with its actual output.

- [ ] **Step 2: Whole-branch review**

Invoke `superpowers:requesting-code-review` on `main..HEAD` with this brief: check CLAUDE.md for meaning drift against `git show main:CLAUDE.md` (every rule), TRADEMARK/GOVERNANCE for legal-term fidelity, glossary vs. spec terminology table, no stray German, link integrity, SVG readability. Fix confirmed findings; re-run Step 1.

- [ ] **Step 3: Hand over to the owner**

Report: what changed, check results, audit findings from Task 9, the `norm-graph.md` naming decision (not in the spec), and any open QUESTIONS. Ask for confirmation before pushing the branch and opening the merge request. After the MR merges: write the MR 2 plan (ADRs) from the final glossary.
