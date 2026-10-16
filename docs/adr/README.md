# normly — Architecture decision records (ADR)

As of: 10.08.2026 · Reference: SRS/SDD v0.2 (redline)

This document records **what** was decided and **why**. The
implementation is in the SRS/SDD; here are the rationales that have no
place there and that, experience shows, are the first to be forgotten.

Status per entry: `accepted` · `preferred` · `open`

---

## ADR-001 — Open-core model instead of a white-label product

**Status:** accepted

**Decision:** An open-source, self-hostable core carries the freely
available knowledge base and the reference graph. Commercial add-on services
build on it and are to be spun off into a separate company.

**Rationale:** The original vision ("knowledge about norms for everyone") and the
white-label business model contradicted each other. Changing the legal form alone
does not solve the copyright problem — even a non-profit organization
that passes on DIN/VDI/DVGW full texts remains a
competitor for these organizations. Only the separation is viable: free is what may be free;
payment is for process, liability certainty and integration.

**Consequence:** The core must not have any dependency on proprietary components
(REQ-OSS-002). The variant "everything in one GmbH" was rejected.

---

## ADR-002 — License model: AGPL-3.0 / Apache-2.0 / ODbL

**Status:** accepted

**Decision:** Core under AGPL-3.0. Client SDKs and API specification under
Apache-2.0. Data and reference graph under an open data license with
share-alike effect (ODbL).

**Rationale:** Through § 13, the AGPL closes the network-use gap —
anyone who operates the core as a hosted service must disclose changes. That
is the protection against a fork by a standardization body or a
large software vendor. Apache-2.0 for SDKs and API specification ensures
maximum reach where no logic worth protecting resides.

**Rejected:** Apache-2.0 as the sole core license (gives the code away without
anything in return to potential competitors). MPL-2.0 (file-based copyleft
can be circumvented by moving code into new files, the SaaS gap stays open —
combines the disadvantages of both sides).

**Important:** The AGPL does not block third-party software integration. A
plugin that talks to a normly instance over HTTP is a separate
program. The AGPL only applies when someone modifies and
operates the server itself.

---

## ADR-003 — Contribution model: DCO instead of CLA

**Status:** accepted

**Decision:** External contributions via the Developer Certificate of Origin.
Every commit carries a `Signed-off-by` line. No transfer of rights.

**Rationale:** The DCO lowers the barrier for contributors and fits the aim
of freely accessible knowledge about norms.

**Knowingly accepted:** This **permanently rules out
dual licensing.** As soon as the first external contribution is in the core, the
rights are distributed and no one can sell a commercial exception license to the
AGPL any longer. This source of revenue is lost.

**Rejected:** CLA (would have enabled dual licensing, was turned down in favor of
community openness). Also rejected: DCO with a permissive
inbound license (contributions under Apache-2.0, shipping under AGPL) — would have
kept relicensing open.

**Open:** Who is the rights holder in the LICENSE and copyright header — a person,
a future Trägerorganisation or a GmbH? Clarify before the first external contribution.

---

## ADR-004 — STACKIT Git as the primary platform, GitHub as contribution facade

**Status:** was partially superseded by ADR-019 (2026-09-05), which rejected the
contribution facade on GitHub (a public presence for issues, pull requests and
visibility, holding no credentials or deployment rights). Since ADR-021
(2026-09-14), the GitHub split originally made here applies again to source
code, CI and registry, but with GitHub as primary instead of as a mere
contribution facade — see ADR-021 for the current state.

**Decision:** STACKIT Git (Forgejo) with STACKIT Pipelines is primary for
source code, build, artifacts, credentials and deployment. GitHub serves as the
public contribution facade: issues, pull requests, visibility. No
credentials, runners, build artifacts or deployment rights there.

**Rationale:** A public image and public source code are
uncritical in terms of sovereignty — what is worth protecting is operations, data and
credentials. The split gives visibility without loss of sovereignty and is
even the stronger argument towards standardization partners: the code is open and
auditable, data and operations are in Germany.

**In practice:** STACKIT Pipelines are largely GitHub Actions compatible,
a later switch of the workflows is cheap. Contributions are accepted in only **one**
place — two parallel issue trackers look like a dead
project.

**Rejected:** GitHub + Vercel as the origin (would have required an exception clause against
our own specification). Pure STACKIT without a public facade
(loss of visibility and external contributions).

---

## ADR-005 — No Vercel, deployment entirely on STACKIT

**Status:** accepted

**Decision:** No Vercel. Next.js as a container (`standalone` output) via
the STACKIT Container Registry, operation initially on a VM with Compose, later
SKE.

**Rationale:** Vercel ties automatic deployments only to GitHub, GitLab
and Bitbucket — Forgejo is not among them, so the convenience advantage is lost
anyway. The extra effort is smallest at the start of the project, and the
US exception clause in the SRS is dropped entirely.

**Side condition:** LLM inference and vector search do not run on
serverless platforms anyway (runtime limits, no GPUs). The core is therefore designed as a
standalone service with an HTTP API.

---

## ADR-006 — PostgreSQL instead of Neo4j for the reference graph

**Status:** accepted

**Decision:** PostgreSQL Flex with pgvector. Graph access encapsulated behind an
abstracted interface (REQ-GRAPH-004), storage technology
interchangeable.

**Rationale:**

1. STACKIT offers no managed Neo4j. Neo4j would have to be operated on SKE ourselves
   — backup, failover, updates included. PostgreSQL Flex provides this out of the box.
2. Neo4j Community (GPLv3) has no clustering and no hot backups; Enterprise
   is proprietary and expensive. Both undermine the self-hosting promise of
   REQ-OSS-002.
3. The queries are shallow (one to three hops, bounded replacement chains).
   Recursive CTEs suffice. Neo4j plays to its strength in deep, variable-length
   traversals — not the pattern here.
4. Graph and embeddings live in the same database, the same transaction,
   the same backup. Keeping two systems in sync is a permanent
   source of errors.

**Valid even at worldwide coverage:** With an estimated 2–4 million documents and
50–200 million edges, this remains uncritical for PostgreSQL. Neo4j does not scale
horizontally through sharding; Postgres can be partitioned by publisher or
jurisdiction.

**The actual scaling risk** is the vector index, not the graph.
At worldwide coverage, several billion text sections are to be expected —
there pgvector becomes the bottleneck much sooner. Therefore encapsulate the retrieval layer
as well.

---

## ADR-007 — Reference graph stays open

**Status:** accepted

**Decision:** The reference graph is not withheld but published under
ODbL — layered into a free and a commercial part.

**Rationale:** Open does not mean unprotected. The database maker's right
(§§ 87a ff. UrhG, German Copyright Act) protects the substantial investment in procurement and
preparation and makes the share-alike clause enforceable: anyone who builds the graph into
their own product must disclose the derived database under the same
terms. For data, this is the counterpart to the AGPL for code.

Secrecy would be the weaker protection — the graph can be reconstructed from the source documents.
Without the graph, all that would remain of the free core is a chatbot over
DGUV/BAuA documents; the Trägerorganisation would have no
reason to exist.

**Dividing line:**

| Free (ODbL) | Commercial |
|---|---|
| Schema, identifiers | Currency guarantee with SLA |
| References between public standards | Section-level references in licensed norms |
| Replacement chains, validity states | Confidence ratings, evidence citations for audits |
| References law → norm | Industry-specific enrichments |
| Periodic dump | SLA API with change notification |

The last point is the economically decisive one: **A monthly dump
and a guaranteed up-to-date API with a liability commitment are different products.
Companies pay for reliability, not for data.**

---

## ADR-008 — Graph-first query processing

**Status:** accepted

**Decision:** Queries are resolved against the reference graph first. A
language model is only invoked when synthesis over running text is needed.

**Rationale:** Structural questions ("what replaces X", "which regulation
references Y") can be answered exactly from the graph — deterministically, in
milliseconds, without token costs. A model call would be more expensive, slower
and more error-prone. Especially with validity and replacement questions,
hallucinations have particularly serious consequences.

**Double gain:** lower inference costs *and* higher reliability exactly
where errors would be most expensive. In addition: caching of identical queries,
a small model for routing, a large one only for complex syntheses, quotas in
free use.

---

## ADR-009 — No personalized advertising

**Status:** accepted

**Decision:** Personalized advertising based on search queries, chat
histories or user profiles is ruled out. Permitted: context-free directory
entries, affiliate on shop links, paid entries in the conformity
directory.

**Rationale:**

- *By the numbers:* A chat session generates hardly any ad slots, but consumes
  several LLM calls with long contexts. A small, German-speaking specialist
  target group at high cost per query — structurally the worst
  combination for advertising financing.
- *Data protection:* The questions are unusually sensitive — a
  safety officer after an accident, a mid-sized company before a
  product launch. That is competitive information and partly liability-relevant.
- *Neutrality:* Whoever says what the recognized state of the art is cannot
  advertise products at the same time. With respect to DIN and VDI, an unnecessary
  point of attack.

**The better lever is the cost side** — see ADR-008.

---

## ADR-010 — Shipping as a container, data separate from the image

**Status:** accepted

**Decision:** Signed, versioned container images plus a runnable
Compose setup. The free knowledge base is **not** part of the image, but
an independently versioned dump that is obtained on first start.

**Rationale:** An AGPL core that no one except the project itself can operate
is practically not open. The image is the proof of
self-hostability — and the same artifact that runs in managed hosting.
The separation of code and data is necessary because norm editions change
considerably more often than the code; otherwise the image grows and every data update
forces a rebuild.

**Registry:** **Addendum 2026-09-14 (ADR-021):** GitHub Container Registry
(GHCR) in the repository `normly/web-app` is the primary registry for the
free core — supersedes the previous addendum of 2026-09-05 (ADR-019, STACKIT
Container Registry exclusively) in turn. STACKIT Container Registry remains
available for artifacts of the commercial layer or later norm data projects,
but is no longer the registry of the core image. Docker Hub
at most later as an independent mirror, should pull limits for anonymous
access become a real problem.

---

## ADR-011 — Internationalization from the start

**Status:** accepted

**Decision:** The reference graph is designed for worldwide coverage from the
start: globally collision-free identifier scheme, language-independent
node identity, national adoptions as relationships, multilingual
designations. License classification **per jurisdiction**, not globally.

**Rationale:** A later rebuild of the identifier scheme is the
most expensive legacy burden imaginable. DIN EN ISO 9001 and BS EN ISO 9001 are the same
document — without language-independent identity, duplicates arise that
make reference chains unusable.

The freely publishable share is **not** globally uniform: § 5 UrhG
applies only in Germany; in the USA the situation tends to be more generous
through the edicts-of-government doctrine; for harmonized
EU norms, CJEU C-588/21 (2024) must be assessed separately. A global
classification would be either unlawful or unnecessarily restrictive.

**Follow-up task:** The legal assessment per jurisdiction is an ongoing
task, not a one-time clarification. It will later need a role or a process.

---

## ADR-012 — No scraping of commercially exploited catalog collections

**Status:** accepted

**Decision:** Catalog and metadata collections of publishers who
exploit them commercially themselves (in particular DIN Media / Nautos, formerly
Perinorm) are obtained **exclusively by contract**. Automated
acquisition is ruled out — even when the collections are publicly
accessible. Implemented as an allowlist in the source register (categories
A–D, REQ-PIPE-002) with a technical block (REQ-PIPE-008).

**Rationale:**

1. *The catalog is the product.* Nautos comprises around 2.35 million records from
   29 countries, including monthly updates by the
   standardization bodies — that is, exactly the catalog including change tracking that
   normly would need. Rebuilding it means attacking the revenue product of exactly the
   organizations with which negotiations are to take place.
2. *Legally.* A norm catalog is a protected database. § 87b UrhG
   prohibits not only the extraction of substantial parts but also the **repeated and
   systematic** extraction of insubstantial parts, insofar as this conflicts with normal
   exploitation — that describes periodic scraping with reconciliation
   exactly. The TDM exception of § 44b does not apply where there is a machine-readable
   rights reservation.
3. *Strategically — the weightiest point.* normly negotiates for
   publishers to provide content **voluntarily** and to receive a share in return
   (ADR-013). Parallel harvesting is the exact opposite of this narrative and
   would damage the negotiations.

**Consequence:** The initial collection comes from freely accessible sources
(REQ-PIPE-009): EU Official Journal via EUR-Lex (lists of harmonized norms, dated
and machine-readable), references from laws and regulations, DGUV and
BAuA registers, work programmes of CEN/CENELEC, catalog data from ISO/IEC.
This is at the same time the most valuable part for the reference graph, because that is where the
references **from the law** are.

**Rejected:** A Nautos license as a data source for our own collection — such
licenses typically exclude reuse in one's own product.
Before such a license, the contract terms would have to be examined closely.

**Not governable by good intentions:** The block is deliberately formulated *technically*
(category D adapters cannot be configured for flagged sources),
not as a policy. As soon as student employees or external
contributors write adapters, the specification decides, not
gut feeling.

---

## ADR-013 — Metadata first: partnership ladder instead of full-text leap

**Status:** accepted

**Decision:** Publishers are first asked for **catalog metadata**,
not for full texts. Full-text supply is the second stage, based
on real attribution figures from the first.

**Rationale:** Metadata costs a publisher almost nothing and brings them
visibility and sales through referrals. Full text is the big hurdle,
metadata the small one. A publisher that delivers monthly metadata deltas
to Nautos anyway has no additional effort with a second delivery.

As soon as the first stage is running, auditable attribution figures are available
(REQ-PART-002/003). This fundamentally changes the full-text conversation: it is
then about a percentage on verifiable figures instead of the question of whether one
believes normly at all.

**Key message for negotiations:** normly does not appear as a competitor that
displaces sales revenue, but as a channel that opens up new revenue and
traceably passes it back.

**First conversation partner:** Austrian Standards (full-text provision
announced).

---

## ADR-014 — Encryption: cryptographic erasure per publisher

**Status:** accepted

**Decision:** Encryption of data at rest for **all** data stores
(database, object storage, indexes, logs, backups). Keys in the
STACKIT Secrets Manager, separate from the data, with rotation and
access logging. **A separate data key per publisher.** In addition, protection
against bulk extraction (rate limiting, quotas, anomaly detection).
→ REQ-SEC-001…004

**Rationale — the actual point is the backups:** REQ-PART-001 promises
that a publisher can withdraw collections **at any time**. REQ-PIPE-005
solves this via the lineage chain for database, index and exports — but
**not for backup copies.** Existing backups still contain the content,
and selective cleanup is practically not feasible.

A data key per publisher closes the gap: contract end → destroy the key
→ content is unreadable everywhere, even in backups, without a single byte
having to be deleted.

**Negotiating argument:** not "we delete reliably", but "we technically *cannot*
read it any longer afterwards". That is qualitatively something different and
considerably more robust in a licensing conversation.

**Side finding:** Chapter 3.3.2 covered only transport encryption. The
wording "vaults or env variables" was factually off — environment variables
are not a secrets manager. Corrected.

---

## ADR-015 — Copy protection: traceability instead of prevention

**Status:** accepted

**Decision:** Licensed full texts are never handed out as a complete file.
Offline use via encrypted, time-limited local storage bound to user and
device. User-specific marking of every display. All three components belong
to the **commercial layer**, not to the core.
→ REQ-DRM-001…004

**Rationale:** Absolute protection is not achievable for text — a screenshot
plus text recognition delivers a usable copy in seconds. Whoever promises
otherwise promises the untenable. Achievable and sufficient are:

1. *Hand out no file.* The damage arises from passed-on PDFs,
   not from reading.
2. *Enable offline use nonetheless.* Without offline capability, the PDF copy
   remains more practical for people on the construction site — then the
   approach misses its purpose.
3. *Attributability.* Does not prevent photographing the screen, but makes it
   traceable. That is exactly the added value compared to today, where a
   circulating PDF copy cannot be attributed to any source.

**Why the commercial layer:** A protection mechanism with exposed
source code is no protection — the circumvention could be read off directly. That is the
only point at which the AGPL and copy protection truly collide; the separation
resolves it. Freely available content is not subject to the restrictions anyway.

**Negotiating argument:** normly does not displace illegal copies through better
protection, but through **better access.** A searchable, linked norm
available offline is more useful than a PDF passed around — and
traceable.

---

## ADR-016 — Mobile: PWA first, native only for licensed content

**Status:** accepted

**Decision:** Phases 0–1 exclusively a **PWA** on the same codebase as
desktop, offline via service worker for free content. **Native app from phase
2/3**, exclusively for licensed offline full texts, as part of the
commercial layer. F-Droid later for the free client.
→ REQ-MOB-001…004

**Rationale:** The driver is **not** the language model but
copy protection. REQ-DRM-002 requires encrypted local storage bound to
user and device. In the browser there is no place where a
key could be kept protected — IndexedDB is inspectable. Native platforms
offer Keychain or Keystore, partly hardware-backed, plus `FLAG_SECURE` against
screenshots on Android.

The PWA/native boundary thus coincides with the free/commercial boundary.

**License conflict resolved:** The terms of use of the Apple App Store are considered
incompatible with AGPL/GPL (cf. the removal of VLC). The commercial app is
therefore a **separate client** that talks to the server only via the API
specified under Apache-2.0 — a separate program, not subject to the AGPL.

**F-Droid** requires fully open-source, reproducible builds without
proprietary components; the DRM components exclude the commercial app
there. Suitable for the free client — as positioning, not as a
channel for reach.

**Corrected:** Chapter 3.5.6 tied the native app to the availability of a
normlyLLM of its own. This coupling was factually wrong.

**Already consider now:** offline layer behind an abstraction (REQ-MOB-003)
— can only be retrofitted later with considerable effort.

**Important distinction — commercial layer ≠ paid access:** The
assignment of the native app to the commercial layer concerns **ownership,
licensing and maintenance**, not user access. The app is free of charge in
the stores; freely available content in it is accessible without an account and without a fee.
Fees are charged exclusively for licensed full texts and their
protected offline provision.

Reasons: An app that asks for money before its first use is not
installed and not tried out. And free use is the channel into
the target group — whoever looks up a DGUV rule on the construction site is later
the one who asks at their company for access to the DIN full texts.

**PWA/app distinction:** Both show the same free content. To avoid duplicate
maintenance for the same user group, the PWA remains the default route
for occasional users; the native app is promoted specifically where
offline use is needed.

---

## ADR-017 — Anonymous base use with a quota instead of an account requirement

**Status:** accepted

**Decision:** Search, reference graph and freely available content are usable **without
an account**, limited by a request quota counted on the server side.
Account required for: higher quotas, histories and bookmark lists, own
uploads, licensed content, offline use, paid services — the
list is **exhaustive**. → REQ-ACC-001…004

**Rationale against a blanket account requirement:**

- It is the highest hurdle in the user journey; whoever has to create an account first
  goes back to Google.
- It contradicts "open to everyone" — and funders and
  standardization partners notice that.
- Operators of their own instances (e.g. a craft guild) would have to run user
  management just to display free standards.
- Without an account, no personal data arises — the simplest form of
  data minimization.

In practice, this produces **more** accounts, not fewer: whoever first
experiences the product signs up voluntarily and with a recognizable benefit in return.

**On the concern about bulk extraction via anonymous access:** The dividing line is the
**content**, not the access path. Anonymously reachable is exclusively what
is freely licensable under REQ-PIPE-004 — and anyone may extract that anyway.
Licensed full texts are **structurally** unreachable anonymously
(REQ-PART-004 authorization check, REQ-DRM-001 no file download,
REQ-DRM-003 mandatory marking). That is not a setting but follows
from the architecture.

**Important to put in perspective:** An account is **no** protection against
bulk extraction — it only makes it attributable. Signed-in users can also
extract systematically, and with more rights at that. The actual protection is
REQ-SEC-004 (rate limiting, anomaly detection, blocking). Likewise,
address-based quota counting can be circumvented by changing addresses; it serves
cost limitation, not security.

**Implementation:** Counting on the server side via a session attribute plus client IP address,
not via cookies or browser storage (both reset in two clicks).
Shared infrastructure with REQ-SEC-004 — one place instead of two.

**Rejected:** Artificial delay of anonymous answers. Harms the impression
more than it saves in costs.

---

## ADR-018 — ML-based structure detection in the ingestion pipeline (Docling)

**Status:** accepted

**Decision:** The ingestion pipeline uses
[Docling](https://github.com/docling-project/docling) instead of pdfplumber for
PDF extraction with immediate effect, including its ML-based layout and
table structure detection (standard pipeline: layout model + TableFormer).
This lifts the non-goal item "no generic document understanding"
previously recorded explicitly in the ingestion spec.

**Rationale:** The first two sources (DGUV, EUR-Lex) get by satisfactorily with
rule-based extraction, but considerably more sources
with unknown, partly more complex layouts will follow. For these, Docling in
any case delivers a cleaner, layout-aware text segmentation than
pdfplumber's plain line output, as well as demonstrably reliable
table structure detection (TableFormer, verified against the real EUR-Lex fixture).

**Important, corrected empirically:** The original expectation that Docling
would automatically detect headings/section structure for *every* future source
and thereby make source-specific rules
superfluous does not hold for plainly formatted documents without visual
heading features — with the DGUV fixture, `§ N` headings come back
as `ListItem`, not as `SectionHeaderItem` (see
`docs/superpowers/specs/2026-08-30-docling-migration-design.md`). For
such sources, boundary detection remains pattern-based, now applied
to Docling's cleanly segmented elements instead of to raw text. The
gain is real (better segmentation, reliable tables, in future
also non-PDF formats without extra effort), but smaller than originally
hoped — every new source must still be checked empirically against a real
sample file to see whether Docling's native classification works
reliably for it.

**Distinction from ADR-008:** ADR-008 forbids the use of a
language model at **query time** for structural questions — for reasons of cost, latency
and hallucination with every single user query. This
decision concerns a different point in time and a different kind of model:
Docling's layout/table model runs **once at ingestion time**, is
**discriminative** (detects structure in existing content), not
**generative** (invents no content, no hallucination risk in the
strict sense) and is deterministically reproducible for the same input.
The result flows into the reference graph as normal, deterministic content
— every later query is still answered exclusively
on the basis of the graph, entirely without a model call. ADR-008 remains unchanged in its
actual scope.

**Implementation:** Model weights are obtained once during the container image build
and baked in — no access to external model repositories at
runtime, in line with the STACKIT-only requirement for operations. Empirically
confirmed: Docling's standard pipeline automatically runs OCR (even without
image content) and, with OCR enabled, downloads additional models from
modelscope.cn for it — a second external source not originally considered,
alongside Hugging Face (the layout/TableFormer model). OCR is therefore
explicitly disabled (`do_ocr=False`), which drops this second model download
entirely instead of also having to bake it into the image.
For details see
`docs/superpowers/specs/2026-08-30-docling-migration-design.md`.

**Rejected:** Docling's VLM pipeline (generative vision-language model)
as the default extraction path — considerably heavier dependency and
operational profile without current need; the discriminative default layout
model is sufficient for today's requirements.

---

## ADR-019 — No more GitHub as contribution facade

**Status:** superseded by ADR-021 (2026-09-14) — source code, CI and
registry are on GitHub again. The entry remains in place as a history of the
rationale.

**Decision:** GitHub is dropped as a target for any future automation.
No push mirror from STACKIT Git to GitHub is set up, and no
acceptance of contributions (issues, pull requests) is planned there any longer. STACKIT Git
is from the start the sole platform for source code, contributions, build and
operations — not merely primary alongside a public facade. The
existing GitHub mirror (`Sn4kez/normly-app`, remote `origin`) remains in place as a
historical snapshot but is no longer actively pushed to.

**Rationale:** Maintaining two platforms in parallel — push mirror,
duplicate issue-tracker discipline, sync effort — is out of all proportion
to the external contribution volume via GitHub, which has so far failed to materialize. One
platform is simpler and fits better with the operational reality, which is
STACKIT-centered anyway.

**Consequence:** Partially supersedes ADR-004 (the STACKIT Git part remains
unchanged in place, the GitHub contribution facade part is dropped). REQ-GIT-002
("Public contribution facade") is thereby obsolete and marked accordingly in
`docs/srs/03-requirements.md`. The push mirror step documented in
`docs/superpowers/specs/2026-09-02-ci-pipeline-design.md` /
`docs/superpowers/plans/2026-09-02-ci-pipeline.md`
is not implemented.

**Rejected:** Keeping GitHub as a pure contribution facade, still maintained
manually, without automation (does not solve the
maintenance-effort problem, only delays the decision).

---

## ADR-020 — Documentation in English instead of German

**Status:** accepted

**Decision:** New documentation (`docs/` content, code reference,
guides) is written in English instead of German with immediate effect. Originally
not intended to be retroactive; the migration of the existing German content
has meanwhile partially taken place (see Addendum 2026-09-14 below).
`docs/superpowers/` does not fall under this rule — the specs, plans and
ledgers there are working documents of the AI-assisted development process,
not documentation for outside readers, and remain in German like CLAUDE.md.

**Rationale:** English is the de facto standard for
open-source documentation. It enables international contributors to
participate, independently of the German-speaking core team — in line with the
open-core model (ADR-001) and the aim that the free core can be
co-sustained from outside. The original rule (documentation in
German) stood in the way of this.

**Not affected:** Code, identifiers and commits were already in
English before (unchanged). The app's own language switch
(`LocaleProvider`, German/English for end users) is a
runtime function, not project documentation, and remains unchanged.
The technical-term exception for terms from the standards domain without an established
English equivalent (e.g. `Normenausschuss`) continues to apply regardless of the
language.

**Consequence:** CLAUDE.md's "Language" section has been adjusted
accordingly. The merge request for the
Zensical documentation site that is already open but not yet merged
(`docs/superpowers/plans/2026-09-11-zensical-documentation-site.md`)
is rewritten in English before the merge, since it counts as "from now
on".

**Addendum 2026-09-14 — migration partially started:** At the owner's request,
translated into English: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`,
`CODE_OF_CONDUCT.md`. The original "not retroactive" rule thus no longer
applies without restriction to all eight originally named files,
but only to the remaining ones: `docs/adr/` (this document),
`docs/srs/`, `GOVERNANCE.md`, `TRADEMARK.md` — their migration remains a
separate, later project, in particular `docs/adr/` and `docs/srs/` because of
their size. No change in content to the four translated files,
only a change of language.

**Addendum 2026-10-15 — full migration:** At the owner's request,
everything in the repository moves to English, including `CLAUDE.md` and
the working documents under `docs/superpowers/`. The exception for
`docs/superpowers/` and `CLAUDE.md` stated above no longer applies. The
migration runs in four merge requests: foundation (root files,
`CLAUDE.md`, diagrams, file names, binding glossary), the ADRs (this
document), the SRS, and `docs/superpowers/`. Terminology is binding and
recorded in `docs/glossary.md`, section "Terminology (binding)". Design:
`docs/superpowers/specs/2026-10-15-english-docs-migration-design.md`.

---

## ADR-021 — Return to GitHub for source code, CI and registry

**Status:** accepted

**Decision:** GitHub (organization `normly`, repository
`github.com/normly/web-app`) is again the primary platform for source code,
CI/CD and container registry (GitHub Actions, GitHub Container Registry) from
14.09.2026. This supersedes ADR-019 entirely — not only the contribution
facade part, but the entire stipulation "STACKIT Git is the sole platform
for source code, contributions, build and operations". STACKIT
Git (`jwokittel/normly-webapp`) is no longer used for source code, CI or
registry. It remains in place and is intended as the platform for the
future hosting of the norms knowledge base as soon as licensed
collections are added — that is a data project, not a code project, and
continues to follow the separation from ADR-010 (code and data versioned separately).

**Rationale:** Owner decision. Collaboration — external as well as internal
— is noticeably easier on GitHub than on the self-hosted
Forgejo setup: tooling, reviewer ecosystem and contributor-friendliness were
already the original reason for ADR-004, before ADR-019 rejected them in favor
of the sovereignty of a single STACKIT platform. The
collaboration disadvantage has had a stronger effect in practice than
expected; the sovereignty requirement itself remains in place, but with
immediate effect applies to operations, user data, the norms knowledge base
and secrets — no longer to the open-source core source code, its CI and its
image registry.

**Consequence:**

- Supersedes ADR-019 entirely and changes ADR-004 (STACKIT instead of GitHub
  as primary) as well as the registry addendum in ADR-010 (STACKIT Container
  Registry instead of GHCR) each in its core point.
- CLAUDE.md's non-negotiable US-services rule continues to apply unchanged to
  operations, user data, the norms knowledge base, secrets management and
  production deployment — STACKIT remains in place for these without
  exception. For source code, CI/CD and container registry of the free core,
  the exception made here applies from now on.
- `docs/srs/03-requirements.md` is to be updated accordingly:
  REQ-GIT-001 (primary platform), REQ-GIT-002 (contribution path), REQ-BUILD-002
  (CI/CD infrastructure), REQ-INST-001 (exception in the running text) and
  REQ-DIST-004 (registry reference).
- The previous GitHub mirror `Sn4kez/normly-app` (local remote
  `github-old`) was a pure snapshot from the ADR-004 era, no longer
  maintained, and is to be distinguished from the new repository
  `normly/web-app` — no automatic connection between the two.
- Open as technical follow-up work, not part of this decision itself:
  port of `.forgejo/workflows/ci.yml` to `.github/workflows/`,
  GHCR credentials and secrets setup in the GitHub repository
  settings. Until then, no CI runs on GitHub.

**Rejected:** Keeping STACKIT Git as the sole platform (status quo
from ADR-019) — the collaboration disadvantage weighs more heavily for the
core source code than the sovereignty gain, while the latter continues to
prevail for operations and data and remains untouched there.

**Addendum 2026-10-09 (ADR-025):** The statement above that STACKIT Git is
intended as the platform for the future hosting of the norms knowledge base
is outdated. The knowledge base is distributed as a signed dump in a publicly
readable STACKIT Object Storage bucket (ADR-025); the separation of
code and data from ADR-010 is unaffected by this. The repository
`jwokittel/normly-webapp` thus no longer has a purpose. **Decided
(2026-10-09): The repository will be deleted**, not archived; the operator
carries this out in the STACKIT portal. The Git remote `stackit` is thus obsolete.
The original wording remains in place as the decision history.

---

## ADR-022 — Operating environment phase 1 and model-origin rule

**Status:** accepted (2026-09-23, amended 2026-10-03)

**Decision:**

1. **Target environment:** one STACKIT VM (`g1a.4d`) with Docker Compose, Caddy
   for TLS, PostgreSQL Flex (single instance, pgvector), Secrets Manager,
   later Object Storage. No SKE, no load balancer. Confirms ADR-005.
2. **LLM inference:** STACKIT AI Model Serving (OpenAI-compatible API,
   region eu01), initial model `google/gemma-4-31B-it`. Ollama remains for
   local development and self-hosting.
3. **Model-origin rule:** Language models used in production are
   open-weight models under an OSI-approved license, operated
   exclusively on STACKIT infrastructure; no request reaches the
   model vendor. European origin is a preference, not a requirement.
   Revisit: as soon as STACKIT offers a European model of suitable
   size, the switch will be examined.
4. **DNS:** the zone `normly.ai` is hosted entirely at STACKIT DNS
   (registrar remains Strato); no more Cloudflare. App at
   `app.normly.ai`.
5. **Mail sending:** SMTP from the existing Strato mail package
   (`noreply@normly.ai`), SPF and DKIM in the STACKIT zone.
6. **Environments:** initially only one production environment on STACKIT; the
   local Compose setup takes on the role of the staging environment.
   Deliberate, temporary deviation from REQ-DIST-001, to be lifted as soon as
   there are users whom a faulty deployment would hit.
7. **Images:** one shared Python base image with all
   `core` dependencies and baked-in embedding weights; no
   splitting of the dependencies.

**Rationale:** The VM with Compose is the cheapest environment and at the
same time the self-hosting artifact from ADR-010. AI Model Serving delivers
GPU inference per token without standing costs; the data goes to STACKIT, not
to the model vendor — weights are a file, not a service. The
origin rule closes the previously unregulated gap that the
default model (Llama, Meta license) was neither openly licensed nor
regulated; a European requirement would have left only a dedicated GPU VM,
since the STACKIT catalog lists no European chat model.
Cloudflare as DNS would have been a US service in the operations chain. The
domain's mail was already at Strato; a second provider would have meant an
MX change.

**Rejected:** Ollama on CPU in production (response times), dedicated GPU VM
(standing costs), European model origin as a requirement (no offering),
subzone delegation only for `app` (Cloudflare would remain authoritative), IONOS
as a second mail provider (MX conflict), splitting the
`core` dependencies into extras (owner decision in favor of
simplicity).

**Consequence:** CLAUDE.md gets a sentence on model origin; REQ-DIST-001
and chapter 3.5.9 of the SRS refer here; `docs/guide/self-hosting.md`
describes the Compose route. Follow-up work: load the embedding model only once
and downsize the VM to `g1a.2d` (TP1a), image pipeline (TP2),
obtaining secrets via AppRole (TP3), rollout/rollback/data version (TP4). Details:
`docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`.

---

## ADR-023 — Image pipeline: GHCR, keyless signing, one version, lock file

**Status:** accepted (2026-10-08)

**Decision:**

1. **Publication:** The five container images (`api`, `chat`,
   `accounts`, `pipeline`, `frontend`) are built in GitHub Actions
   and stored as public packages under `ghcr.io/normly/web-app/`
   (confirms ADR-021). Builds run on push to `main` (tags `edge`,
   `sha-<short>`), on Git tags `vX.Y.Z` (`X.Y.Z`, `X.Y`, `latest`) and
   manually — never on pull requests.
2. **Signing:** cosign keyless via GitHub OIDC. No key material
   is generated or kept; the short-lived certificate binds the
   signature to repository, workflow and commit. In addition, per image,
   SLSA provenance and SBOM from BuildKit (REQ-GIT-005).
3. **Versioning:** One version for all five images; the annotated
   Git tag `vX.Y.Z` is the single source. The version fields of the
   packages are set to the same value in the release commit; the
   workflow checks that they match.
4. **Reproducibility:** The four Python packages form a
   uv workspace with one `uv.lock`; Torch comes exclusively from the
   CPU wheel index; base images are pinned by digest, model weights (e5,
   Docling) by commit, and sit in a build stage of their own
   (REQ-BUILD-001). Deliberately left open are timestamps in the layers
   and the apt packages of the base layer; bit-identical images are thus
   not yet achieved.

**Rationale:** The trust anchor of the keyless signature — the public
Sigstore infrastructure (Fulcio, Rekor) — is **operated by the Linux
Foundation, a non-profit organization.** This distinguishes it
qualitatively from the commercial US services in the build chain that
ADR-021 permits for the free core, and is a lighter burden than
key management, rotation and re-signing on loss. The shared
version reflects what is actually tested: the services only in
combination, `api` and `chat` even from one base image; a rollback
is thus a single step. Doing without PR builds keeps the pipeline
lean; a broken Dockerfile shows up loudly and without harm after the merge
(`edge` stays where it is, the release tag fails). Without
pinned weights, the same Git tag could produce different embeddings than
the data version that TP4 imports.

**Rejected:** own cosign key pair (key management, storage
outside GitHub, re-signing on loss); version per package
(tested combination no longer readable, one tag per package per release);
image build on pull requests (full build per PR, path filter misses
code changes); pip-tools (four lock files with possible drift, no
clean index separation for Torch).

**Consequence:** `docker compose up -d` pulls published images,
`--build` remains the local route; `docs/guide/self-hosting.md` describes
obtaining the images and verifying the signatures, `docs/guide/releasing.md`
the release procedure, `CONTRIBUTING.md` the uv development environment.
REQ-BUILD-001, REQ-DIST-004 and REQ-GIT-005 refer here. Signature verification
as a mandatory step before start on the VM follows with the rollout script
(TP4). Details:
`docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md`.

---

## ADR-024 — Rollout, rollback and backup on the single VM

**Status:** accepted (2026-10-09); builds on ADR-010, ADR-014 and ADR-023

**Context:** The production VM currently builds its images from source code;
there is no rollback point. User data is backed up only by the Flex backup
(daily, 30 days, provider-internal). STACKIT credentials must
not be stored on GitHub (ADR-021), so a push rollout from CI is ruled
out. The signatures from ADR-023 are of use only once the VM verifies them
before start (REQ-GIT-005).

**Decision:**

1. **Trigger:** Rollout manually via SSH: `normly-deploy deploy vX.Y.Z`. The
   script is kept timer-capable; there is no timer.
2. **Verification before start:** `cosign verify` of all five images against the
   identity `images.yml@refs/tags/vX.Y.Z` of the release workflow. Compose file
   and script assets travel in the signed `pipeline` image and are taken from the
   verified `pipeline@<digest>`. The verified digests are
   recorded (digest pinning); after `compose pull` the pulled
   digests must match the verified ones, otherwise nothing starts.
3. **Procedure:** read the current tag and knowledge base version,
   pre-rollout backup (no rollout without a confirmed upload), `pull`,
   `up -d --wait`. The current tag is rejected; as long as a
   failed rollout is recorded (`state/failed_rollout`), no new
   `deploy` starts (deliberate override: remove the marker file).
   There is no automatic way back.
4. **Rollback restores images and data to their state before the rollout.**
   Because Alembic migrations run forward only, the schema is
   rebuilt: stop services, drop all tables of the schema `public`
   (list from the database; the schema remains so that pgvector is
   preserved), `migrate` with the previous image, import the knowledge base
   in the dump version active at the time (before the user data, because of the
   foreign keys), the retired IDs of the backup
   (`exchange import-tombstones`, see ADR-026), user data with
   `pg_restore --data-only`, start the previous release. Beforehand the
   script checks that the Alembic revision of the backup matches the Alembic head of the
   previous image, that the recorded knowledge base dump is
   retrievable and verifiable (signature, model, checksums; without a usable
   public key, abort before anything is changed) and that the
   tombstone file of the backup is retrievable, decryptable and valid
   (a backup whose `meta.json` promises the file but which lacks it
   counts as damaged: abort; an older backup without such a promise leads to
   a warning, the rollback continues), and requires
   entering the target tag (or `--yes`). The private key is provided only
   for the run (`--age-identity FILE`). If the
   rollback fails after the drop, the script gives hints for the restore;
   calling it again is safe.
5. **Backup:** the user data tables (`exchange tables user`) and, as a
   second encrypted file, the retired IDs
   (`<base>.tombstones.age`, ADR-026; never content, rights or user data).
   Both `age`-encrypted on the VM with the public key, upload
   via `rclone` into a private STACKIT Object Storage bucket. The private
   key never resides on the VM. Upload order: `meta.json`,
   `dump.age`, `tombstones.age`, `.sha256`; the checksum covers both
   encrypted files and is the commit marker; only with it does
   a backup count. `meta.json` carries `"tombstones": true`.
6. **Retention:** 7 daily, 2 monthly (in each case the newest daily
   backup of the two most recent calendar months), 3 pre-rollout backups. The
   retention applies to both files of a backup: the cleanup deletes
   `.sha256`, `meta.json`, `tombstones.age`, `dump.age` in this order
   and skips objects that are not in the bucket (older backups
   without a tombstone file). It counts only committed backups and deletes
   orphans (without `.sha256`, including a lone `tombstones.age`) only after
   one day. In addition, Flex's 30-day backup
   of the entire database remains the operational safety net.
7. **Restore test:** manual and documented (`docs/guide/operations.md`),
   once after the build, a monthly reminder thereafter.

**Rationale:**

- *Manual trigger:* A human decides on the migration window.
  Otherwise migrations would run unattended, and a timer would need
  "highest tag" logic and a stability window.
- *Rollback = rebuild:* Migrations are forward only. A pure
  image rollback would require an expand/contract discipline that does not exist;
  a pure data restore would leave the new schema in place.
- *Back up only user data:* The knowledge base is reproducible via the dump
  (ADR-025); a daily full dump would be wasteful at double-digit GB,
  whereas the user data is small and irreplaceable.
- *Key separation:* The VM can write backups but not
  decrypt them (the VM's bucket access includes reading, because the rollback
  downloads the backup; the private key is missing).
  Even with a compromised VM the backups remain protected, unlike
  with server-side encryption, whose key lies with the provider next to the
  data (CLAUDE.md: keys never next to the data).
- *Digest pinning:* `cosign verify` checks what the tag points to at that
  moment. A tag moved between verification and `pull` would otherwise bypass the
  verification.
- *Commit marker:* An aborted upload must neither count as a backup
  nor displace an older, valid one.

**Rejected:** timer with auto-rollout; pure image rollback with
expand/contract discipline; exclusively server-side encryption;
daily full dump; only pre-rollout dumps; weekly backups (benefit
beyond 7 days small).

**Consequences:**

- A rollback discards all changes since the pre-rollout backup
  (accounts, chats, watchlists). The script warns and requires confirmation.
- The rollback duration grows with the knowledge base (re-import).
- Prerequisite: the knowledge base in production changes only through
  dump import, never through ingestion on the VM (at the same time a prerequisite for
  downsizing the VM, TP1a).
- `pg_dump`, `psql` and `pg_restore` run on the host; `NORMLY_DATABASE_URL`
  must be resolvable there (managed database, not the bundled profile).
  The database password appears in the process arguments (assumption: single-tenant VM;
  hardening deferred). Docker Compose 2.20 or later is required (`--wait-timeout`).
- Open: Cryptographic erasure at contract end (ADR-014) for licensed
  collections is a task of the commercial layer; they must be excluded from backups
  or encrypted per publisher. The secrets flow via
  AppRole (TP3) is out of scope. PITR and encryption of the Flex backups
  are to be clarified. **Object lock (decision 2026-10-10): none for now.**
  According to the operator, STACKIT offers Object Lock only after a
  project-wide Compliance Lock and only when the bucket is created;
  irreversible (to be checked against the STACKIT documentation before implementation). Arguments
  against it: irreversibility before the first live acceptance, effect on the whole
  project, conflict with the in-house retention (`normly-backup` deletes old
  backups) and with the promise not to let deleted user data come back
  (rollback replays deletions of the last 90 days; a longer lock
  would retain them longer). Accepted residual risk: with stolen credentials
  of the VM, backups could be deleted; they cannot be read
  (`age`, private key kept elsewhere). Mitigation to be examined: separate
  credentials for the VM without delete permission. Reassessment after the live acceptance; a
  later second bucket with a lock and a period of at most 90 days would be
  possible. The interplay
  of `docker compose up --wait` with the one-off `migrate` service and the
  query of the Alembic head have so far only been tested against mocks, until
  the live acceptance.

Details: `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md`,
operations: `docs/guide/operations.md`.

---

## ADR-025 — Knowledge base dump as exchange format

**Status:** accepted (2026-10-09); amends ADR-010, changes the statement on the
knowledge base in ADR-021 (see the addendum there)

**Context:** ADR-010 separates code and data; REQ-DIST-004 requires a
separately versioned dump that is obtained on first start. So far the
knowledge base is created by ingestion on the VM; neither self-hosters nor
a rollback can reproduce it.

**Decision:**

1. **Format:** Parquet per table plus `manifest.json` and the Ed25519 signature
   `manifest.json.sig`. The manifest records the exchange schema version
   (independent of Alembic), dump version and timestamp, embedding model with
   name and pinned revision, vector dimension (1024), source deliveries, and
   checksum together with row count per file.
2. **Access:** Export and import run through the repository layer
   (`KnowledgeExchangeRepository`), not through Postgres tools.
3. **Signature:** Ed25519 in Python (`cryptography`), verified in the core. The
   public key lives in the repository. The key ceremony is still
   pending; until then the key must be specified. It is resolved in this
   order: `--public-key`, environment variable
   `NORMLY_KB_PUBLIC_KEY_FILE`, bundled key.
4. **Distribution:** publicly readable STACKIT Object Storage bucket with
   calendar version `kb/<version>/` and `kb/latest`. A version is
   immutable. `fetch` downloads only from `NORMLY_KB_BASE_URL` (https, for
   localhost also http) and checks version and paths.
5. **Import:** atomic and idempotent; the caller commits, the
   imported version is recorded in the database. What the new version
   no longer contains is handled according to ADR-026, never blocked by
   user data: detach citations, delete content, set tombstones, withdraw
   deliveries, then insert or update. A dump without documents
   is rejected as long as the database holds documents, unless
   `--allow-empty` is set.
6. **Checks on import:** signature, exchange schema version, model name
   **and** model revision (`NORMLY_EMBEDDING_MODEL_REVISION`), dimension,
   checksums. On a mismatch, abort; no silently wrong embeddings.
   The same checks run without a database as the subcommand `verify
   (--from DIR | --fetch VERSION)`; the rollback calls it before the first
   destructive step so that an unverifiable dump is not noticed only after
   the tables have been dropped.
7. **Export gate:** the rights classification as the single gate, evaluated
   across all jurisdictions. Exported is what has a non-revoked
   classification with `may_process` and `may_export_free`,
   whose delivery is not withdrawn, and whose source has category A, B
   or D and is not a commercially exploited catalog. Missing
   classification means do not export. Merged works are exported together
   with their target so that the redirect is preserved. User data and
   licensed collections are never included.
8. **First start:** the Compose service `kb-import` (profile `tools`) runs
   `import --fetch latest`.

**Rationale:**

- *Parquet instead of `pg_dump` (owner decision, against the original
  recommendation):* ADR-006 and CLAUDE.md require database access only through the
  repository layer so that the storage technology stays interchangeable;
  `pg_dump` is a Postgres artifact and bypasses it.
- *Public product (REQ-DIST-004):* A format not bound to our
  Alembic revision survives schema changes. With `pg_dump`, every
  self-hoster would have to find the matching application version.
- *Lineage:* A table-by-table export with the source delivery per row keeps the
  withdrawal of a delivery traceable in the dump as well.
- *Parquet instead of NDJSON:* Embeddings (1024 floats, about 4 KB per section)
  would otherwise be unwieldy.
- *Price:* more code (export, import, exchange schema), slower import,
  idempotency to be established ourselves. We accept that.
- *Ed25519 in the core instead of cosign/minisign:* The import runs in the
  `pipeline` image and at the self-hoster's; an additional binary would enlarge
  the image and create a second installation hurdle. Keyless signing does
  not work because the dump is created locally, not in CI.
- *Object Storage instead of Git:* large binary files and anonymous access are
  unwieldy in a Git repository; the knowledge base thus stays on STACKIT
  (CLAUDE.md).
- *Import with tombstones instead of blocking:* see ADR-026.

**Rejected:** `pg_dump` of the knowledge base; delta dumps (the format leaves
them open, they are not built); STACKIT Git as storage; an additional
Git manifest as history (second system); NDJSON.

**Consequences:**

- ADR-021 receives an addendum; CLAUDE.md and REQ-GIT-005 have been adjusted.
- `docs/guide/self-hosting.md` describes the import, `docs/guide/operations.md`
  export, signature and publication.
- The export gate reads the rights classification and introduces no second
  check path.

**Personal names (decided 2026-10-09):** The export replaces personal names
with the role `normly maintainers`. Affected are
`source.responsible_person` and `rights_classification.classified_by`; both
columns carry the constant `PUBLISHED_ROLE` in every exported row. The
replacement happens in the export statement of the repository layer, that is, at the
location of the export gate, and changes neither the manifest nor the exchange schema (no
version increment). The dump never carries a name; the source registration in the code contains only
a placeholder, and names that an ingestion operator enters live only
in that operator's own database. An import overwrites the two columns with the
role label: production, which loads the public dump, therefore carries the
label, never names; a re-export of an imported state is row-identical.
Never import a dump into the ingestion database: the upsert there overwrites
the names irrevocably. Also masked is
`classified_by="pipeline:automatic"`; the public dump thus does not distinguish
between automatic and human classification (deliberate
compromise; the label is a role and not a statement about human
review).
A test searches for a unique name in all rows, all Parquet files
and the manifest.

**Open items:**

- **Delta dumps** are not built.
- **Key ceremony:** generation, safekeeping and publication of the
  signing key are pending.

Details: `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md`.

---

## ADR-026 — Handling user data on knowledge base import

**Status:** accepted (2026-10-09); replaces the import's blocking rule
from ADR-025

**Context:** The import of a knowledge base dump aborted with
`ImportBlockedError` as soon as user data (`watchlist`, `notification`,
`notified_edge`, `chat_message_citation`) referenced a row that the new
dump no longer contains. For a legally required withdrawal (delivery
withdrawn, classification revoked) that is wrong: it must not fail because of
user data (CLAUDE.md, "Carry lineage along"). Finding from the code:
no user data table stores copyrighted content; they
are only references (`work_id`, `edge_id`, `document_id`, `segment_id`); the text
of a citation is fetched from `segment` only when it is read.

**Decision:** A withdrawal always wins; a user reference never blocks
an import. What the dump no longer contains is handled by class:

| Class | Tables | Handling |
|---|---|---|
| Tombstone (ID, no content) | `work`, `document`, `edge` | Row stays, `retired_at` is set; edges are additionally revoked (`revoked_at`). User references remain valid. |
| Provenance | `source`, `delivery` | Are never deleted; a missing delivery receives `withdrawn_at`. |
| Content/derivation | `document_designation`, `document_title`, `rights_classification`, `segment`, `embedding`, `document_embedding` | Are physically deleted. |

Procedure in `replace_knowledge_base`, in this order: load the dump's
keys; detach citations (`chat_message_citation.segment_id` becomes `NULL` for segments
that the dump does not contain); delete missing content in reverse
foreign-key order; retire missing tombstones; mark missing
deliveries with `withdrawn_at`; insert or update the dump
(rows of the tombstone classes from the dump receive `retired_at = NULL`:
return); write the import record. Deleting and retiring run **before**
inserting, so that a re-delivery with new IDs does not collide with natural
unique keys (designation, title, partial index of active
edges). `ImportBlockedError` (with `.step`) remains only as a last safeguard for
an unexpected foreign key.

- `retired_at` (migration 0033; `work`, `document`, `edge`) is not an
  exchange column: dump format and `EXCHANGE_SCHEMA_VERSION` remain unchanged.
- `retired_at` is not a mandatory filter. A retired document no longer has a
  rights classification; every gate-bound read site (the single gate)
  thereby excludes it. No second check path arises.
- Protection against an empty dump: A dump without documents is rejected as long as the
  database holds documents (`allow_empty`, or `--allow-empty` on the CLI, lifts this).
- A test walks through all foreign keys of every table outside the knowledge base
  that point to the knowledge base (fail-closed), not only those of the
  user data tables, so also `identity_resolution_case`: every target must
  belong to a class or have an explicit resolution rule.
- Notification: In production a revocation deletes the classification, so the
  rights-change path of `notify-watchers` would see nothing. New
  notification type `no_longer_available` (migration 0034, table
  `notified_retirement`, `trigger_type` to VARCHAR(19)): `notify-watchers`
  creates one notification per retired document of a watched work, only
  for withdrawals after watching began; the dedup key contains
  `retired_at` (a renewed withdrawal after a return is notified again). No
  link; e-mail subject "Ein beobachtetes Regelwerk ist nicht mehr verfügbar";
  bell "Nicht mehr verfügbar" / "No longer available". `delete_account`
  removes the account's `notified_retirement` rows.

**Rationale:** The promised withdrawal must never depend on a human or on
user data. Deleted content is no longer readable, in production as well as after the
backups expire; tombstones carry only IDs. No
user reference is lost because the knowledge base changes.

**Rejected:**

- Blocking with a cleanup tool: the withdrawal would wait for a human.
- Adjusting or deleting user references: data loss without benefit, since only
  references are affected.
- Pure tombstones for content too: the withdrawal would only be logical; the text
  would remain readable in the database and backups.
- Designation and title as part of the tombstone: they collide on a
  re-delivery with the natural unique keys (finding in review);
  the document keeps publisher, number, edition and part as its ID.

**Rollback and backup (extension 2):** `normly-deploy rollback` (ADR-024)
rebuilds the database and imports the older dump version. Tombstones
are in no dump; user rows that point to them would violate the foreign key on
restore. Therefore every backup contains a second,
`age`-encrypted file `<base>.tombstones.age`:

- *Content:* JSON (`format` 1, `created_at`, `rows` per table in
  foreign-key order) with all rows from `work`, `document` and
  `edge` whose `retired_at` is set, plus the closure over the
  foreign-key parents within `source`, `delivery`, `work`, `document`,
  `edge`. The closure is computed from the ORM foreign keys, not
  hard-wired, and takes in only parents, never children. All columns, including
  `retired_at` and `revoked_at`. Never content, rights or user data.
  `source.responsible_person` may be included; in production it is the
  published role name (imports overwrite it), a real name
  only in a file from an ingestion database. It lives only in the
  encrypted backup.
- *Creation and check:* in the container (`exchange export-tombstones`, stdout),
  checked on the host before encryption (JSON object, `format` 1, `rows`
  with exactly the five tables, each a list). An invalid output aborts
  the backup.
- *Restore:* in the rollback after the knowledge base import and **before**
  `pg_restore` (`exchange import-tombstones`, JSON on stdin, in the image of the
  previous release). Inserting in foreign-key order with
  `ON CONFLICT DO NOTHING`; existing rows remain unchanged;
  `work.merged_into_work_id` is deferred. Inserted rows from `work`,
  `document`, `edge` receive `retired_at` (the backed-up value; for living
  parents the file's `created_at`) and thus count as retired. They have
  no classification; every gate-bound read site excludes them. A
  later normal import that contains the row sets `retired_at` back
  to `NULL`.
- *Pre-check:* The rollback downloads, decrypts and checks the
  tombstone file before the banner, the dump after the confirmation and before the
  stop; before the deletion both are present and decrypted. If
  `meta.json` says `"tombstones": true` but the file is missing, the backup counts as
  damaged (abort). An older backup without such a promise remains usable: the
  rollback warns clearly (a foreign-key error is possible if
  user data points to retired documents) and continues.
- *Not restored:* content and rights of retired documents; only
  IDs. That is intended; the withdrawal remains effective.
- *`revoked_at`:* On a retired edge, `revoked_at` is the
  **import time**, not the time of the revocation at the producer. It
  is not an event date and must not be read as one.

**Consequences / open:**

- A tombstone keeps only `origin_issuer`, `origin_number`, `edition` and
  `part`. Every interface that lists tombstones must fall back on these.
- On re-delivery after a revocation, ingestion creates a **new**
  document node (designations are deleted, `find_by_designation` finds
  nothing). Watches and notifications stay with the tombstone and do not carry over to
  the new node. Product and identity decision, open.
- The producer's export gate leaves out a document whose originating
  delivery was revoked, even after a re-delivery. Open.
- Dumps must come from one lineage with stable IDs. A newly
  built producer database with new IDs can collide with leftover
  tombstones (partial index of active edges, among others) and ends in
  `ImportBlockedError`.
- Retention and expiry of tombstones are open (also after ADR-027).
- The rights-change notification (`RIGHTS_CHANGE`) for pure changes of
  rights values, without the document disappearing, continues to arise at the
  producer, not in production.
- The protection against an empty dump trusts the manifest's row counts; the
  manifest is signed.

Details: `docs/superpowers/specs/2026-10-09-user-data-on-kb-import-design.md`.

---

## ADR-027 — Lifecycle of user data

**Status:** accepted (2026-10-10); builds on ADR-014, ADR-017, ADR-024 and
ADR-026

**Context:** Personal data should be stored only if an
account needs it, and only for as long as the purpose exists; data subjects should be able to
view and delete their data, and a deletion should survive a
restore from backups. The inventory of
2026-10-10 showed gaps:

- Anonymous chats were stored (`chat_session`/`chat_message`, cookie
  `normly_session` with a 90-day lifetime) and never deleted, although the server
  does not need them to answer: every question is answered on its own.
- `account_session` and `account_token` were never deleted (the expiry time
  was only checked); abandoned registrations stayed forever; unread
  notifications likewise.
- There was no way to delete individual chat histories.
- The rollback (ADR-024) restores user data from the backup time:
  accounts and histories deleted in the meantime reappeared.
- The export (`GET /v1/accounts/export`) was incomplete: the
  watchlist named only `work_id`, citations were missing, and the
  chat session token (a secret) was in the export.

**Decision:**

*Principle.* Only what an account needs is stored. Periods are
named constants in one place (`core/src/normly_core/retention.py`) and
are enforced by an idempotent cleanup command.

*Anonymous chat without storage.* `POST /v1/chat` without a valid account identity
writes nothing to the database and answers with `session_token: null`. A
chat token without a valid account is ignored. For anonymous
use the frontend sets no chat cookie and removes an existing one; the conversation lives
only in the browser tab. The linking "attach the anonymous session to the account on
sign-in" is deliberately dropped. The quota is unaffected by this: it is
counted server-side via the rate limiting (cookie `normly_anon_id` plus
client IP address, `rate_limit_bucket`), not via chat sessions
(REQ-ACC-003). Existing anonymous histories (`account_id` empty) are deleted by the
cleanup command.

*Chats with an account* remain until deleted by the person or by
account deletion. `DELETE /v1/chat/sessions/{id}` deletes one of the person's own histories
(204; 404 for someone else's or an unknown ID; 401 without sign-in),
`DELETE /v1/chat/sessions` all of their own (`{"deleted": n}`); the sidebar
offers both with confirmation.

*Data inventory.* All tables of the user data group (`USER_TABLES`):

| Table | Purpose | Personal data | Period | Deletion path |
|---|---|---|---|---|
| `account` | account, sign-in | e-mail, name, password hash, avatar | until account deletion; **abandoned registration** (e-mail never verified, older than 30 days, without a Google link, without any account session) 14 days after a delivered advance warning e-mail, never without it | account deletion by the person (cascades to all tables with an account reference); cleanup command |
| `account_session` | signed-in session | account reference, session token; no IP, no user agent | 7 days after expiry | cleanup command; account deletion |
| `account_google_identity` | link to Google sign-in | Google ID, account reference | until account deletion | account deletion |
| `account_token` | one-time token (verification, reset, magic link) | account reference | 24 hours after expiry or use | cleanup command; account deletion |
| `oauth_state` | CSRF protection of the Google sign-in | none (random value) | unchanged (1 hour) | existing cleanup |
| `watchlist` | watchlist | account reference, interests | until account deletion or removal by the person | person; account deletion |
| `notification` | notifications | account reference, watched work | read 60 days, unread 365 days after creation | cleanup command; account deletion |
| `notified_edge`, `notified_retirement`, `rights_notification_baseline` | bookkeeping against duplicate notifications | account reference | until account deletion | account deletion |
| `chat_session`, `chat_message`, `chat_message_citation` | chat histories with an account | the person's questions and answers | no period; anonymous legacy rows (`account_id` empty) are deleted | person (per history or all); account deletion; cleanup command for legacy data |
| `rate_limit_bucket` | rate limiting and quota | pseudonymous key from browser ID and client IP address | unchanged (10 minutes) | existing cleanup |
| `deletion_log` | deletion log (see below) | none: only kind, ID, time | 90 days | cleanup command |

The avatar lives in `account` and disappears with the account or on
removal. The data inventory is to be reassessed as soon as `account_session`
stores IP addresses or user agent (not the case today).

*Abandoned registrations.* The rule is deliberately narrower than "unverified":
Google accounts are never marked as verified (`email_verified_at` stays
empty), and accounts with a password can sign in even without verification. An
account in use therefore has a Google link or at least one
`account_session` row (even an expired one, as long as it has not been deleted;
the session's deletion period begins only 7 days after expiry) or a
sign-in within the last 30 days: `account.last_login_at` is set on every
session creation and, unlike the session row, survives
sign-out. Only an account without all of that, never verified and older than 30 days,
counts as abandoned. This
also hits a password account that was used and then paused for a long time,
as soon as its sessions are removed; therefore no account is deleted silently:
the cleanup command first sends a bilingual advance warning e-mail (date of
deletion, sign-in URL from `NORMLY_PUBLIC_BASE_URL`, no token) and sets
`account.deletion_warned_at` only after successful sending. Deletion happens
14 days after that at the earliest (strictly), and only if the account then still meets all
conditions. Sign-in, verification or a Google link make the
account "not abandoned" again; the next run resets the warning.
Prerequisite is an SMTP relay (`NORMLY_SMTP_*`): without a relay or if
sending fails, no warning is ever sent and thus no account is ever deleted; the sending
is retried in the next run. An account is never
warned and deleted in the same run (order: reset, delete, warn). The
deletion run locks the candidates and re-checks the condition together with the warning time,
so that a concurrent verification, sign-in or
Google link is not lost. `deletion_warned_at` and
`last_login_at` are not exported. The mail names the date as
"at the earliest on", because the daily run can shift the time by up to one
day.

*Cleanup command.* `python -m normly_core.pipeline cleanup-user-data` enforces all
periods of the table (sessions, tokens, abandoned registrations,
read and unread notifications, anonymous legacy chats,
deletion log), is idempotent and prints only counters. The systemd timer
`normly-cleanup` (daily 04:00 UTC) starts via `scripts/normly-cleanup`; the
script skips the run with exit code 0 as long as `state/deploy.lock`
exists. `cleanup-notifications` remains as a command.

*Export (access request).* `GET /v1/accounts/export` delivers synchronously as JSON:
profile, avatar (data URL), watchlist with readable document IDs
(all documents of the work, including retired ones), notifications, and chats
with answer type and citations (readable document ID and segment ID). Not
included: `session_token` (instead the session ID), password hash,
tokens and bookkeeping.

*Deletion log and replay.* Table `deletion_log(kind, entity_id,
deleted_at)` (`kind` is `account` or `chat_session`; migration 0035). The
entry is created in the same transaction as every deletion (account deletion,
deleting a history, cleanup of abandoned registrations), contains no
personal data, is part of the user data backup and is pruned after
90 days (see Consequences). The core offers
`python -m normly_core.exchange export-deletions --since <ISO-8601>` (JSON on
stdout) and `replay-deletions` (JSON on stdin; applies the deletions again via the
normal deletion functions, idempotent; entries already missing are
still written to the log); `replay-deletions --check` reports without a
database whether the image knows the command.

In the rollback (ADR-024): The script reads the deletions since the
backup time **minus one hour** directly from the database (host `psql`
and `python3`, no startable release image needed; the core command remains for
manual use) (safety margin in the script; a deletion applied twice
is harmless because UUIDs are never reused). This first export feeds the
banner and the decision on `replay-deletions --check` in the image of the
**previous** release (exit code 2 means "not supported", any other
error aborts). After the services are stopped and before the DROP, a second
export follows; this document is applied after `pg_restore` and the tombstone restore
by the previous image. If the second export fails, the
rollback aborts before the DROP (database unchanged, hint about restarting). Before the
DROP the list is written to `$STATE/rollback-deletions.json` (0600); a
renewed run after an error after the DROP merges it with the fresh export
(union by kind and ID, earliest time) and deletes the
file only once the previous release is running healthy. `normly-cleanup` and
`normly-backup` run with the tag from `state/current_tag`, never with the
Compose default `edge`.
A missing table `deletion_log` (release before this feature) counts as an empty
list. If the previous image does not know the command, the banner names the count and
the first 20 `kind:id`; the complete list lies in
`$STATE/rollback-pending-deletions.json` (0600) and must be deleted again
by hand.

**Rationale:**

- Data minimization: What the server does not need to answer is not
  stored. This fits ADR-017 ("without an account, no
  personal data arises"): anonymous use remains complete without the
  history accruing.
- Short, named periods for technical data (sessions, tokens,
  notifications), no period for content that the person creates themselves
  and can delete themselves at any time.
- The rule for abandoned registrations never deletes silently: without a delivered
  advance warning and a 14-day period, every account stays; a wrongly deleted account
  would be data loss, one deleted too late only a stored
  record. The price is the dependency on SMTP.
- The deletion log contains only IDs. It is therefore not itself a
  copy of the deleted data and can run along as part of the user data backup;
  without the ID, a deletion would remain ineffective after a rollback or restore.
- The export remains synchronous and readable (readable document IDs instead of internal IDs, where
  possible); a secret such as the chat token is not the person's data.

**Rejected:**

- *A period for chats with an account too:* The person creates them, can
  delete them themselves, and they are the purpose of the account ("histories", REQ-ACC-004).
  A silent deletion would be a loss of function without a data protection gain.
- *Short-term storage of anonymous sessions:* The server does not need them;
  any storage would be data without purpose, and the cookie would remain necessary.
- *Cryptographic erasure per account in backups:* A key per account
  in the backup format would be a large change to backup and restore; the
  deletion log with replay achieves the same result for this purpose after
  restore, and the after-effect is limited in time. (For
  licensed collections, ADR-014 remains authoritative.)
- *Asynchronous export via e-mail link:* More infrastructure (queue,
  storage, link expiry) and more stored copies, without the scope
  requiring it.
- *Deleting all unverified accounts:* Google accounts are never "verified" and
  password accounts can sign in unverified; the rule would
  delete accounts in use.

**Consequences / open:**

- *After-effect in backups.* A deletion takes effect in the database immediately, in
  backups only when they expire: Flex 30 days; own `age`-encrypted
  backups up to roughly two months (7 daily, 2 monthly anchors,
  3 pre-rollout backups). The deletion log ensures that deletions
  survive a rollback or restore. It is pruned after 90 days, longer than
  daily and monthly backups are kept. A pre-rollout backup can become
  older if no rollout follows for a long time; if a restore is made from a backup
  that is older than 90 days, the deletion log can no longer re-apply the
  deletions from the time in between.
- *Expert review.* The periods are decisions of the project and should
  be reviewed by a data-protection professional; this document is not
  legal advice.
- Privacy policy and record of processing activities (Art. 30
  GDPR (DSGVO)) are separate legal texts and not part of this work.
- *Tombstones* (ADR-026): retention and expiry remain open.
- A previous release without `replay-deletions` needs manual re-deletion
  (see above); this also applies to the restore test and the
  emergency restore from Flex (operations guide).
- The cleanup timer checks `state/deploy.lock` but does not take the lock
  itself. If an orphaned lock is left behind, it skips silently every day.
- Deleting inactive accounts after a period with advance warning by e-mail is not
  implemented.
- `account_session` stores neither IP nor user agent; if that changes,
  the data inventory and period are to be reassessed.
- The linking "anonymous → account on sign-in" is dropped; whoever chatted anonymously
  keeps the history only in the open tab.

Details: `docs/superpowers/specs/2026-10-10-user-data-lifecycle-design.md`,
operations in `docs/guide/operations.md`.

---

## Open items

| Topic | Status | Next step |
|---|---|---|
| Spin-off GmbH | preferred, not accepted | Review under tax law and association law before founding |
| Legal form of the Trägerorganisation (e.V. / eG / alternative) | open | An eG could bring standardization bodies in as members instead of opponents |
| Rights holder in the copyright header | open | Clarify before the first external contribution |
| License agreement Trägerorganisation → GmbH | open | Must be on customary market terms, otherwise a risk to non-profit status |
| RDF/JSON-LD export with SKOS | proposed | Storage format and publication format are separable |
| Attribution weighting model for graph answers | open | Is a publisher owed anything when an answer was given without full text? Recorded as a category of its own, to be clarified contractually |
| Rights reservations per source (§ 44b Abs. 3 UrhG) | ongoing task | Review dated and documented in the source register, with a follow-up date |
| Legal assessment per jurisdiction | ongoing task | Needs a responsible role in the medium term, not a one-off clarification |
| Apple commission on digital subscriptions | open | In the EU there are now alternatives via external payment routes — check before the store release |
| Retention periods of the backup copies | open | (User data: maximum periods recorded in ADR-027.) Determines how long a destroyed key must be kept on hand before backups expire |
| STACKIT repository `jwokittel/normly-webapp` | decided (2026-10-09): delete | The operator deletes it in the STACKIT portal (addendum to ADR-021); then remove the entry |
| Personal names in the public knowledge base dump | decided (2026-10-09): role `normly maintainers` | Implemented in the export (ADR-025); remove the entry after the first public dump |
| Retention and expiry of tombstones | open | Whether retired IDs are limited in time; ADR-027 did not decide it (ADR-026) |
| Identity on re-delivery after revocation | open | New document nodes do not take over the tombstones' watches; product and identity decision (ADR-026) |
| Signing key of the knowledge base dump | open | Key ceremony, check the public key into the repository (ADR-025) |
| Expert review of the retention periods for user data | open | By a data-protection professional; in addition, privacy policy and record of processing activities as separate legal texts (ADR-027) |
| Deleting inactive accounts with advance warning | open | Not implemented; decide period and warning e-mail (ADR-027) |
| Backups for licensed collections | open | Cryptographic erasure (ADR-014) for the commercial layer; clarify Flex PITR; deliberately no object lock for now (ADR-024) |

**Note:** The legal assessments in this document are a
working basis, not legal advice. In particular, the construction
Trägerorganisation/GmbH, the design of the license agreement and the
copyright assessment per jurisdiction belong before an expert review.
