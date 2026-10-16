# Design: Language rule correction — documentation in English

## Context

Until now, CLAUDE.md prescribed: "Documentation and user interface in
German, multilingual support planned." (wording at the time). On this basis, the new
Zensical documentation site (PR #30, see
`docs/superpowers/plans/2026-09-11-zensical-documentation-site.md`)
was written entirely in German — including a final review that
even specifically corrected nav labels from English to German, because
that was the rule in force at the time.

The owner has corrected this rule: documentation must be in
English, without exception. This is a reversal of the previous requirement, not a
misunderstanding of the old rule.

## Decision

**From now on, new documentation is written in English.** This concerns
`docs/` content, code reference, guides — not code/identifiers/commits
(those were already English before; CLAUDE.md did not change here) and
not CLAUDE.md itself (stays German as working instructions).

**Only from now on, not retroactively.** Existing German content is not touched in
this project. This concerns in particular:

- `README.md`
- `docs/adr/README.md` (ADR-001 to ADR-019, entirely German)
- `docs/srs/*.md` (78 requirements, entirely German)
- `CONTRIBUTING.md`, `SECURITY.md`, `GOVERNANCE.md`, `TRADEMARK.md`,
  `CODE_OF_CONDUCT.md`

This migration is a separate, considerably larger follow-up project and
expressly **not** part of this spec.

**The technical-term exception remains in place, independent of language.** CLAUDE.md
already allowed keeping German terms from the standards domain where there is
no established equivalent (`Normenausschuss` as an example). This
already applied independently of the language of the surrounding documentation and now applies
in exactly the same way in English running text (e.g. "the
`Normenausschuss`" instead of an invented translation).

**The user interface is not affected.** The frontend already has
a real de/en language switch (`LocaleProvider`,
`frontend/src/lib/i18n/provider.tsx`) — it stays unchanged. This
decision concerns only running-text documentation, not the app UI.

## Non-goals

- No retroactive translation of README/ADR/SRS/CONTRIBUTING/etc. —
  a separate follow-up project.
- No change to CLAUDE.md's own language (stays German).
- No change to the app language switch (de/en stays as it is).

## Implementation

### 1. CLAUDE.md — correct the rule text

In the "Sprache" (Language) section, the sentence "Documentation and user interface
in German, multilingual support planned" (wording at the time) is replaced by a rule that
prescribes documentation in English, takes over the technical-term exception
unchanged, and makes clear that this does not refer to the
existing app language switch. CLAUDE.md itself stays
entirely German — only this one rule paragraph now describes a
different requirement than before.

### 2. ADR-020 — document the decision

A new entry in `docs/adr/README.md`, after ADR-019, with status
"accepted". **Written in German**, as an interim measure — consistent
with ADR-001 to ADR-019, until this file as a whole is translated in the later migration
project.

**Decision:** New documentation (docs/ content, code reference,
guides) is written in English instead of German with immediate effect. Not
retroactive — existing German content is not migrated; that is
a separate follow-up project.

**Rationale:** English is the de facto standard for
open-source documentation. It enables international contributors to
participate, independently of the German-speaking core team — in line with the
open-core model (ADR-001) and the aim that the free core can be
co-sustained from outside. The original rule (documentation in
German) stood in the way of this.

**Not affected:** Code/identifiers/commits were already English before
(unchanged). The app's own de/en language switch
(`LocaleProvider`) is a runtime function for end users, not
project documentation, and stays unchanged. The technical-term exception
for terms from the standards domain without an established English equivalent
(e.g. `Normenausschuss`) continues to apply regardless of the language.

### 3. PR #30 — rewrite the existing documentation site content in English

The PR is not yet merged — the complete PR content counts as "from
now on", not as protected existing content. Affected files (branch
`docs/zensical-documentation-site`):

| File | Approach |
|---|---|
| `zensical.toml` | `site_description` and all `nav` labels from German to English (back again — they had been specifically corrected to German in the final review shortly before, which was right at that point). |
| `docs/index.md` | Translate, structure/links unchanged. |
| `docs/guide/getting-started.md` | Translate. |
| `docs/guide/self-hosting.md` | Translate; the ADR-010 link target stays unchanged (still links to the German ADR page — that is fine, the ADR migration is not part of this spec). |
| `docs/concepts/norm-graph.md` | Translate. |
| `docs/concepts/license-model.md` | Translate, incl. the category table (A–D) and the new ADR-014 paragraph. |
| `docs/glossary.md` | Translate — the **title goes from "Glossar" to "Glossary"**; technical terms without an established English equivalent such as `Normenausschuss` follow the technical-term exception from CLAUDE.md. `Referenzgraph` does **not** fall under it — the term already has an established English equivalent in "Reference graph", which is used consistently on the other pages of the site (`index.md`, `norm-graph.md`, `license-model.md`), and is translated accordingly instead of being kept as a term. |
| `docs/reference/*.md` | **No change** — already English (`# normly-core`, `Reference graph data model...`, `::: normly_core`). |

After the translation: verify the build again (`zensical build`; the
known 3 warnings from `docs/superpowers/specs/*.md` remain
unchanged, no new warnings caused by the translation). The
previously verified anchor links (ADR-008, ADR-006, ADR-002, ADR-007,
ADR-012, ADR-011, ADR-014, ADR-010) do not change through the translation,
since they point to the (still German) `docs/adr/README.md` —
check them again after the translation anyway, in case something has shifted because of
text changes around the links.

## Error handling

No new error behavior — the same verification method as in the
original build-out (build check + targeted grep/anchor checks per
page, see the original plan). No `--strict` (taken over unchanged from the
original project; the rationale given there still applies).
