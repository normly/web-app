---
name: specifications
description: Use when locating, changing, or reviewing normly's requirements, architecture decisions, or verification documentation.
---

# Specifications and decision records

Use this skill for the procedure to update requirements and decision records.
For the contributor-facing explanation of how the SRS, ADRs, code, tests, and
guides fit together, see the
[developer onboarding guide](../../../docs/guide/developer-onboarding.md).

## Change a requirement

1. Search the SRS index in `docs/srs/README.md` and the requirements in
   `docs/srs/03-requirements.md` for the existing requirement. Prefer updating
   the existing ID over creating a duplicate.
2. Keep requirement IDs stable. If a new requirement is necessary, assign an
   ID in the appropriate group and include a clear statement, rationale,
   acceptance criteria, and verification method consistent with neighboring
   requirements.
3. Update the index in `docs/srs/README.md` when adding, removing, or renaming a
   requirement; keep its count and group tables accurate. Update
   `docs/srs/05-verification.md` when verification coverage or method changes.
4. Update affected code, tests, API or user documentation in the same change,
   or explicitly identify follow-up work. Check links and requirement IDs
   before finishing.

## Record an architecture decision

Add a new numbered ADR to `docs/adr/README.md` when a change makes a material
architectural or strategic choice whose rationale future contributors need.
Follow the neighboring entries' structure:

- status (`accepted`, `preferred`, or `open`, using the terms established in
  `docs/adr/README.md`),
- decision,
- rationale and important trade-offs,
- consequences and alternatives rejected,
- links to affected requirements and implementation guidance.

When a decision replaces an earlier one, mark the earlier ADR as superseded
and link both entries. Update the SRS if the decision changes a requirement,
not merely because a requirement refers to an ADR. Add unresolved actions to
the open-items list where appropriate.

## Keep the change reviewable

- Update requirements, ADRs, tests, and operational documentation together
  when they describe different aspects of the same changed behavior.
