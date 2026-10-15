# Migrating all repository content to English — design

Date: 2026-10-15
Status: approved by the owner, 2026-10-15

## Goal

Everything in the repository is in English: documentation, specs, plans,
ADRs, the SRS, root-level project files, `CLAUDE.md`, diagram labels and file
names. This completes the migration begun in ADR-020 (and its addendum of
2026-09-14), which left `docs/adr/`, `docs/srs/`, `GOVERNANCE.md`,
`TRADEMARK.md` and `docs/superpowers/` in German.

## Decisions already made

- Translate everything, including `docs/superpowers/` and `CLAUDE.md`.
- Rename German file names to English and fix all references.
- Four merge requests, in sequence (see below).
- When a word or passage is uncertain, stop and ask instead of choosing.

## Scope

**In scope** — German or mixed-language files, as of 2026-10-15:

- Root: `GOVERNANCE.md`, `TRADEMARK.md`, `MAINTAINERS.md`, `CLAUDE.md`
- `docs/adr/README.md` (all ADRs, ~10,100 words)
- `docs/srs/` (`README.md`, chapters 01, 02, 03, 05, 06; ~13,300 words)
- `docs/normly_Entwicklungsphasen.svg`, `docs/normly_Verarbeitungskette.svg`
- `docs/superpowers/specs/` — 29 German specs
- `docs/superpowers/plans/` — 5 German plans (2026-10-04 to 2026-10-10)
  and 2 mixed plans (2026-09-11, zensical and language policy)

**Unchanged:**

- Code identifiers, requirement IDs (`REQ-…`), ADR numbers, product names
  (*normly*, *Normtracker*, *Perinorm*), `Normenausschuss`,
  `Trägerorganisation`.
- Names of German statutes and standards (§ 5 UrhG, DIN, DGUV, BAuA). At the
  first mention per document, add an English gloss in parentheses, e.g.
  "§ 5 UrhG (German Copyright Act)".
- Quoted strings of the German UI locale and German source text in fixtures.
- Git history, commit messages already written.

## Terminology (binding)

| German | English |
|---|---|
| Norm, Normen | norm, norms |
| Regelwerk, Regelwerke | standards |
| Normen und Regelwerke / Normen- und Regelwerkswissen | norms and standards / knowledge about norms and standards |
| Herausgeber | publisher |
| Referenzgraph | reference graph |
| Wissensbasis, Wissensbestand | knowledge base |
| Rechteklassifikation | rights classification |
| Rechtsraum | jurisdiction |
| Ausgabestand | edition |
| Quelllieferung | source delivery |
| Abstammung | lineage |
| Herkunft (attribute) | provenance |
| Rücknahme | withdrawal |
| Rollback (deployment) | rollback |
| Sicherung | backup |
| Tombstone | tombstone |
| Verarbeitungskette | processing chain |
| Beitragsfassade | contribution facade (explained at first mention) |
| Nachtrag | addendum |
| Akzeptanzkriterium, Abnahmekriterium | acceptance criterion (both; the SRS uses them as synonyms) |
| Begründung / Entscheidung / Konsequenz | Rationale / Decision / Consequence |
| Konto-, Kontolöschung | account deletion |
| Normenausschuss, Trägerorganisation | unchanged (German loanwords, see glossary) |

**Compounds follow their stem.** Rechtsnorm → legal norm, EU-Normen → EU norms,
Regelwerkswissen → knowledge about standards, Regelwerksreihen → standards
series, Regelwerksverzeichnisse → standards registers. If a compound has no
obvious reading under this rule, ask.

**Disambiguation.** "norm" and "standard" are separate terms here and are
never interchangeable: *norm* is the German *Norm*, *standard* is the German
*Regelwerk*. "Standard" in its ordinary technical sense ("standard library",
"standard output") is untouched.

## Already-English documents: minimal term sweep

README, CONTRIBUTING, `docs/index.md`, `docs/glossary.md`, `docs/concepts/`,
`docs/guide/` already use "standards" in a sense that is correct in English.
The owner confirmed (2026-10-15) that this stays. MR 1 therefore only
replaces the German loanword *Regelwerk(e)* where it still appears in these
documents (e.g. README: "standards and Regelwerke") with "standards" — a term
change only, no rewording — and adds the glossary entries.

The already-English documents in `docs/superpowers/` are historical working
papers and are **not** swept; only files translated in MR 4 follow the new
terms.

## File renames (MR 1)

| Old | New |
|---|---|
| `docs/srs/01-einfuehrung.md` | `01-introduction.md` |
| `docs/srs/02-produktueberblick.md` | `02-product-overview.md` |
| `docs/srs/03-anforderungen.md` | `03-requirements.md` |
| `docs/srs/05-verifikation.md` | `05-verification.md` |
| `docs/srs/06-anhaenge.md` | `06-appendices.md` |
| `docs/concepts/lizenzmodell.md` | `docs/concepts/license-model.md` |
| `docs/normly_Entwicklungsphasen.svg` | `docs/normly_development-phases.svg` |
| `docs/normly_Verarbeitungskette.svg` | `docs/normly_processing-chain.svg` |

Done with `git mv`, followed by a repository-wide search for the old names
and a fix of every inbound link (README, `docs/srs/README.md`, ADRs, specs,
plans, `docs/` navigation). Filenames of specs and plans (dated, topic slugs)
are already English except `datenmodell-referenzgraph-schema`
(2026-08-11 spec and plan), which becomes `data-model-reference-graph-schema`.

Heading anchors in `docs/adr/README.md` change when headings are translated
(MR 2); inbound anchors are fixed in the same MR.

## Merge requests

1. **Foundation.** This spec's glossary content; terminology section in
   `docs/glossary.md` (including the norm/standard and lineage/provenance
   distinctions); translation of `GOVERNANCE.md`, `TRADEMARK.md`,
   `MAINTAINERS.md`, `CLAUDE.md`; both SVGs; all file renames above; term
   sweep of the already-English public docs (leftover *Regelwerk* only); update of the "Sprache" /
   "Language" section in `CLAUDE.md` to "everything in English". Also a sample
   audit of non-Markdown files (comments, configs) for stray German; findings
   are reported to the owner, not fixed unasked.
2. **ADRs.** `docs/adr/README.md`, plus an addendum to ADR-020 closing the
   migration, plus fixing inbound anchor links.
3. **SRS.** `docs/srs/` chapter by chapter; chapter 03 in sections.
4. **Working documents.** `docs/superpowers/specs/` and `plans/` as listed
   above.

Each MR is pushed and opened only after explicit confirmation (pipeline runs
are billed).

## Process per MR

- Translate in chunks (large files by chapter or section) against the binding
  terminology. A term missing from the glossary stops the work; the question
  goes to the owner, the answer is added to the glossary.
- Faithful translation only. No content changes, no corrections of the
  original; inconsistencies in the source are carried over and reported
  unless the glossary resolves them (e.g. the two "acceptance criterion"
  words).
- Mechanical checks per file against the original: same number of headings,
  tables, code blocks and list items; identical set of `REQ-…` and `ADR-…`
  IDs; identical set of link targets (after rename mapping); no umlauts and
  no German function words left outside quoted German text.
- An independent review pass compares a sample of passages with the original
  for drift in meaning. A final whole-branch review precedes merge.
- Verification before completion: link check over the changed files, the
  documentation-site build if it includes the changed files, and the checks
  above.

## Risks

- **Silent meaning drift** in legal or architecture passages (rights
  categories, takedown, key separation). Mitigation: review sample is biased
  towards ADR-009 to ADR-016 and SRS chapter 3 requirements on rights,
  licensing and withdrawal.
- **Broken links** from renames and anchors. Mitigation: repository-wide
  search and automated link check.
- **norm/standard confusion** while translating. Mitigation: the glossary
  distinction, checked by hand in review, no blind search-and-replace.
- **Intermediate mixed-language state** between MRs. Accepted.

## Out of scope

Translation of the German UI locale, source-language text in fixtures, any
change to commit history, and any rewrite of English documents beyond the term
sweep.
