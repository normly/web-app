# Governance

## Guiding principle

The free core of normly should be able to exist independently of the economic
interests of individual participants. This is why stewardship and
commercial exploitation are kept separate.

## Structure

**Trägerorganisation** (normly e.V.) — holds the trademark, open data and source code, is
responsible for the free core and for relationships with publishers and the
community.

**Commercial company** *(planned, not yet founded)* — operates paid services:
managed hosting, compliance instances, integrations, licensed collections. It
licenses from the Trägerorganisation on customary market terms.

This separation is the reason why the core must not depend on proprietary
components: the free core must be able to keep existing without the commercial
side.

## Roles

**Contributors** — everyone who contributes something: code, data,
corrections, documentation, translations. No formal prerequisite other than the
DCO signature.

**Maintainers** — review contributions and approve requirements in their
area; they do not merge. Admitted by the Lead Maintainers after a sustained
contribution over a longer period. The current list is in `MAINTAINERS.md`.

**Lead Maintainers** — the only ones who merge, into `develop` and into
`main`; decide on architecture (ADRs) and releases, decide when the
maintainers cannot reach agreement, and are responsible for compliance with
the architecture principles. If the Lead Maintainers disagree, the board of
normly e.V. decides.

## Decisions

As a rule by consensus within the affected area. Anything that finds no
consensus is discussed among the maintainers; if it remains disputed, the
Lead Maintainers decide, and if they disagree, the board of normly e.V.

**Architecture decisions** are documented as ADRs in [docs/adr/](docs/adr/) —
with the rationale and the rejected alternatives. A decision without a
documented rationale is not a decision that has been made.

Significant changes are put up for discussion as an issue before
implementation.

## What is not up for discussion

Some commitments are a precondition for the project to fulfil its purpose.
They cannot be changed by a single pull request, only by an ADR with the
explicit approval of the Trägerorganisation:

- License model (AGPL-3.0 core, Apache-2.0 SDKs, ODbL data)
- DCO as the contribution model
- Independence of the core from proprietary components
- Free access to freely licensable content without an account
- Exclusion of personalized advertising
- Data storage and operation in Europe

## Changes to this document

Through a pull request, with the approval of the majority of the maintainers
and of the Trägerorganisation.
