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

## ADR-004 — STACKIT Git as the leading platform, GitHub as contribution facade

**Status:** was partially superseded by ADR-019 (2026-09-05), which rejected the
contribution facade on GitHub (a public presence for issues, pull requests and
visibility, holding no credentials or deployment rights). Since ADR-021
(2026-09-14), the GitHub split originally made here applies again to source
code, CI and registry, but with GitHub as leading instead of as a mere
contribution facade — see ADR-021 for the current state.

**Decision:** STACKIT Git (Forgejo) with STACKIT Pipelines is leading for
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
(GHCR) in the repository `normly/web-app` is the leading registry for the
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
   standardization organizations — that is, exactly the catalog including change tracking that
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

**Decision:** Licensed full texts are never shipped as a complete file.
Offline use via encrypted, time-limited local storage bound to user and
device. User-specific marking of every display. All three components belong
to the **commercial layer**, not to the core.
→ REQ-DRM-001…004

**Rationale:** Absolute protection is not achievable for text — a screenshot
plus text recognition delivers a usable copy in seconds. Whoever promises
otherwise promises the untenable. Achievable and sufficient are:

1. *Ship no file.* The damage arises from passed-on PDFs,
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
offer Keychain and Keystore respectively, partly hardware-backed, plus `FLAG_SECURE` against
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

**Take into account already now:** offline layer behind an abstraction (REQ-MOB-003)
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
(REQ-PART-004 authorization check, REQ-DRM-001 no file shipping,
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
actual sense) and is deterministically reproducible for the same input.
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
as the standard extraction path — considerably heavier dependency and
operational profile without current need; the discriminative standard layout
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
operations — not merely leading alongside a public facade. The
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

**Addendum 2026-09-14 — migration partially started:** At the user's request,
translated into English: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`,
`CODE_OF_CONDUCT.md`. The original "not retroactive" rule thus no longer
applies without restriction to all eight originally named files,
but only to the remaining ones: `docs/adr/` (this document),
`docs/srs/`, `GOVERNANCE.md`, `TRADEMARK.md` — their migration remains a
separate, later project, in particular `docs/adr/` and `docs/srs/` because of
their size. No change in content to the four translated files,
only a change of language.

---

## ADR-021 — Rückkehr zu GitHub für Quellcode, CI und Registry

**Status:** beschlossen

**Entscheidung:** GitHub (Organisation `normly`, Repository
`github.com/normly/web-app`) ist ab dem 14.09.2026 wieder die führende
Plattform für Quellcode, CI/CD und Container-Registry (GitHub Actions,
GitHub Container Registry). Das löst ADR-019 vollständig ab — nicht nur den
Beitragsfassade-Teil, sondern die gesamte Festlegung „STACKIT Git ist die
alleinige Plattform für Quellcode, Beiträge, Build und Betrieb". STACKIT
Git (`jwokittel/normly-webapp`) wird nicht mehr für Quellcode, CI oder
Registry verwendet. Es bleibt bestehen und ist als Plattform für das
künftige Hosting der Normen-Wissensbasis vorgesehen, sobald lizenzierte
Bestände hinzukommen — das ist ein Datenprojekt, kein Code-Projekt, und
folgt weiter der Trennung aus ADR-010 (Code und Daten getrennt versioniert).

**Begründung:** Nutzerentscheidung. Die Kollaboration — externe wie interne
— ist auf GitHub spürbar einfacher als auf dem selbst gehosteten
Forgejo-Setup: Tooling, Reviewer-Ökosystem und Beitragsfreundlichkeit waren
schon der ursprüngliche Grund für ADR-004, bevor ADR-019 sie zugunsten der
Souveränität einer einzigen STACKIT-Plattform verworfen hatte. Der
Kollaborationsnachteil hat sich in der Praxis stärker ausgewirkt als
erwartet; die Souveränitätsanforderung selbst bleibt bestehen, gilt aber ab
sofort für Betrieb, Nutzerdaten, die Normen-Wissensbasis und Secrets — nicht
mehr für den quelloffenen Kern-Quellcode, dessen CI und dessen
Image-Registry.

**Konsequenz:**

- Löst ADR-019 vollständig ab und ändert ADR-004 (STACKIT statt GitHub
  führend) sowie den Registry-Nachtrag in ADR-010 (STACKIT Container
  Registry statt GHCR) auf ihren jeweiligen Kernpunkt.
- CLAUDE.md's nicht-verhandelbare US-Dienste-Regel gilt unverändert für
  Betrieb, Nutzerdaten, Normen-Wissensbasis, Secrets-Management und
  Produktions-Deployment — dafür bleibt STACKIT ohne Ausnahme. Für
  Quellcode, CI/CD und Container-Registry des freien Kerns gilt ab jetzt
  die hier getroffene Ausnahme.
- `docs/srs/03-requirements.md` ist entsprechend zu aktualisieren:
  REQ-GIT-001 (führende Plattform), REQ-GIT-002 (Beitragsweg), REQ-BUILD-002
  (CI/CD-Infrastruktur), REQ-INST-001 (Ausnahme im Fließtext) und
  REQ-DIST-004 (Registry-Verweis).
- Der bisherige GitHub-Spiegel `Sn4kez/normly-app` (lokaler Remote
  `github-old`) war ein reiner, nicht mehr gepflegter Schnappschuss aus der
  ADR-004-Ära und ist vom neuen Repository `normly/web-app` zu
  unterscheiden — kein automatischer Zusammenhang zwischen beiden.
- Offen als technische Folgearbeit, nicht Teil dieser Entscheidung selbst:
  Port von `.forgejo/workflows/ci.yml` nach `.github/workflows/`,
  GHCR-Zugangsdaten und Secrets-Einrichtung in den GitHub-Repository-
  Einstellungen. Bis dahin läuft auf GitHub keine CI.

**Verworfen:** STACKIT Git als alleinige Plattform beibehalten (Status quo
aus ADR-019) — der Kollaborationsnachteil wiegt für den Kern-Quellcode
schwerer als der Souveränitätsgewinn, während dieser für Betrieb und Daten
weiterhin überwiegt und dort unangetastet bleibt.

**Nachtrag 2026-10-09 (ADR-025):** Die Aussage oben, STACKIT Git sei als
Plattform für das künftige Hosting der Normen-Wissensbasis vorgesehen, ist
überholt. Die Wissensbasis wird als signierter Dump in einem öffentlich
lesbaren STACKIT-Object-Storage-Bucket verteilt (ADR-025); die Trennung von
Code und Daten aus ADR-010 bleibt davon unberührt. Das Repository
`jwokittel/normly-webapp` hat damit keine Aufgabe mehr. **Entschieden
(2026-10-09): Das Repository wird gelöscht**, nicht archiviert; der Betreiber
führt das im STACKIT-Portal aus. Der Git-Remote `stackit` ist damit hinfällig.
Der ursprüngliche Wortlaut bleibt als Entscheidungsverlauf stehen.

---

## ADR-022 — Betriebsumgebung Phase 1 und Modellherkunftsregel

**Status:** beschlossen (2026-09-23, ergänzt 2026-10-03)

**Entscheidung:**

1. **Zielumgebung:** eine STACKIT-VM (`g1a.4d`) mit Docker Compose, Caddy
   für TLS, PostgreSQL Flex (Einzelinstanz, pgvector), Secrets Manager,
   später Object Storage. Kein SKE, kein Load Balancer. Bestätigt ADR-005.
2. **LLM-Inferenz:** STACKIT AI Model Serving (OpenAI-kompatible API,
   Region eu01), Startmodell `google/gemma-4-31B-it`. Ollama bleibt für
   lokale Entwicklung und Self-Hosting.
3. **Modellherkunftsregel:** Produktiv eingesetzte Sprachmodelle sind
   Open-Weight-Modelle unter OSI-anerkannter Lizenz, betrieben
   ausschließlich auf STACKIT-Infrastruktur; keine Anfrage erreicht den
   Modellhersteller. Europäische Herkunft ist Präferenz, nicht Pflicht.
   Wiedervorlage: sobald STACKIT ein europäisches Modell in passender
   Größe anbietet, wird der Wechsel geprüft.
4. **DNS:** die Zone `normly.ai` liegt vollständig bei STACKIT DNS
   (Registrar bleibt Strato); kein Cloudflare mehr. App unter
   `app.normly.ai`.
5. **Mailversand:** SMTP aus dem bestehenden Strato-Mailpaket
   (`noreply@normly.ai`), SPF und DKIM in der STACKIT-Zone.
6. **Umgebungen:** zunächst nur eine Produktionsumgebung auf STACKIT; das
   lokale Compose-Setup übernimmt die Rolle der Staging-Umgebung.
   Bewusste, befristete Abweichung von REQ-DIST-001, aufzuheben, sobald es
   Nutzer gibt, die ein fehlerhaftes Deployment treffen würde.
7. **Images:** ein gemeinsames Python-Basis-Image mit allen
   `core`-Abhängigkeiten und eingebackenen Embedding-Gewichten; keine
   Aufteilung der Abhängigkeiten.

**Begründung:** Die VM mit Compose ist die günstigste Umgebung und zugleich
das Self-Hosting-Artefakt aus ADR-010. AI Model Serving liefert
GPU-Inferenz pro Token ohne Dauerkosten; die Daten gehen an STACKIT, nicht
an den Modellhersteller — Gewichte sind eine Datei, kein Dienst. Die
Herkunftsregel schließt die bisher ungeregelte Lücke, dass das
Standardmodell (Llama, Meta-Lizenz) weder offen lizenziert noch
geregelt war; europäische Pflicht hätte nur eine eigene GPU-VM übrig
gelassen, da der STACKIT-Katalog kein europäisches Chat-Modell führt.
Cloudflare als DNS wäre ein US-Dienst in der Betriebskette gewesen. Die
Mail der Domain lag bereits bei Strato; ein zweiter Anbieter hätte einen
MX-Wechsel bedeutet.

**Verworfen:** Ollama auf CPU in Produktion (Antwortzeiten), eigene GPU-VM
(Dauerkosten), europäische Modellherkunft als Pflicht (kein Angebot),
Subzonen-Delegation nur für `app` (Cloudflare bliebe autoritativ), IONOS
als zweiter Mailanbieter (MX-Konflikt), Aufteilung der
`core`-Abhängigkeiten in Extras (Nutzerentscheidung zugunsten der
Einfachheit).

**Konsequenz:** CLAUDE.md erhält einen Satz zur Modellherkunft; REQ-DIST-001
und Kapitel 3.5.9 der SRS verweisen hierher; `docs/guide/self-hosting.md`
beschreibt den Compose-Weg. Folgearbeiten: Embedding-Modell nur einmal
laden und VM auf `g1a.2d` verkleinern (TP1a), Image-Pipeline (TP2),
Secrets-Bezug per AppRole (TP3), Rollout/Rollback/Datenstand (TP4). Details:
`docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`.

---

## ADR-023 — Image-Pipeline: GHCR, keyless Signatur, eine Version, Lock-Datei

**Status:** beschlossen (2026-10-08)

**Entscheidung:**

1. **Veröffentlichung:** Die fünf Container-Images (`api`, `chat`,
   `accounts`, `pipeline`, `frontend`) werden in GitHub Actions gebaut
   und als öffentliche Pakete unter `ghcr.io/normly/web-app/` abgelegt
   (bestätigt ADR-021). Gebaut wird bei Push auf `main` (Tags `edge`,
   `sha-<kurz>`), bei Git-Tags `vX.Y.Z` (`X.Y.Z`, `X.Y`, `latest`) und
   manuell — nie bei Pull Requests.
2. **Signatur:** cosign keyless über GitHub-OIDC. Kein Schlüsselmaterial
   wird erzeugt oder verwahrt; das kurzlebige Zertifikat bindet die
   Signatur an Repository, Workflow und Commit. Dazu je Image
   SLSA-Provenance und SBOM aus BuildKit (REQ-GIT-005).
3. **Versionierung:** Eine Version für alle fünf Images; der annotierte
   Git-Tag `vX.Y.Z` ist die einzige Quelle. Die Versionsfelder der
   Pakete werden im Release-Commit auf denselben Wert gesetzt, der
   Workflow prüft die Übereinstimmung.
4. **Reproduzierbarkeit:** Die vier Python-Pakete bilden einen
   uv-Workspace mit einer `uv.lock`; Torch kommt ausschließlich aus dem
   CPU-Wheel-Index; Basis-Images sind per Digest, Modellgewichte (e5,
   Docling) per Commit gepinnt und liegen in einer eigenen Build-Stufe
   (REQ-BUILD-001). Bewusst offen bleiben Zeitstempel in den Schichten
   und die apt-Pakete der Basisschicht; bit-identische Images sind damit
   noch nicht erreicht.

**Begründung:** Der Vertrauensanker der keyless Signatur — die öffentliche
Sigstore-Infrastruktur (Fulcio, Rekor) — wird von der **Linux Foundation
betrieben, einer Non-Profit-Organisation.** Das unterscheidet ihn
qualitativ von den kommerziellen US-Diensten in der Build-Kette, die
ADR-021 für den freien Kern erlaubt, und wiegt leichter als
Schlüsselpflege, Rotation und Neusignierung bei Verlust. Die gemeinsame
Version bildet ab, was tatsächlich getestet wird: die Dienste nur in
Kombination, `api` und `chat` sogar aus einem Basis-Image; ein Rollback
ist damit ein Handgriff. Der Verzicht auf PR-Builds hält die Pipeline
schlank; ein kaputtes Dockerfile fällt nach dem Merge laut und ohne
Schaden auf (`edge` bleibt stehen, der Release-Tag schlägt fehl). Ohne
gepinnte Gewichte könnte derselbe Git-Tag andere Embeddings erzeugen als
der Datenstand, den TP4 importiert.

**Verworfen:** eigenes cosign-Schlüsselpaar (Schlüsselpflege, Ablage
außerhalb von GitHub, Neusignierung bei Verlust); Version je Paket
(getestete Kombination nicht mehr ablesbar, ein Tag je Paket je Release);
Image-Build bei Pull Requests (voller Build je PR, Pfadfilter übersieht
Codeänderungen); pip-tools (vier Lock-Dateien mit möglicher Drift, keine
saubere Index-Trennung für Torch).

**Konsequenz:** `docker compose up -d` zieht veröffentlichte Images,
`--build` bleibt der lokale Weg; `docs/guide/self-hosting.md` beschreibt
Bezug und Signaturprüfung, `docs/guide/releasing.md` den Release-Ablauf,
`CONTRIBUTING.md` die uv-Entwicklungsumgebung. REQ-BUILD-001,
REQ-DIST-004 und REQ-GIT-005 verweisen hierher. Die Signaturprüfung als
Pflichtschritt vor dem Start auf der VM folgt mit dem Rollout-Skript
(TP4). Details:
`docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md`.

---

## ADR-024 — Rollout, Rollback und Sicherung auf der Einzel-VM

**Status:** beschlossen (2026-10-09); baut auf ADR-010, ADR-014 und ADR-023

**Kontext:** Die Produktions-VM baut ihre Images heute aus dem Quellcode; es
gibt keinen Rollback-Punkt. Nutzerdaten sind nur durch die Flex-Sicherung
gesichert (täglich, 30 Tage, anbieterintern). STACKIT-Zugangsdaten dürfen
nicht auf GitHub liegen (ADR-021), ein Push-Rollout aus der CI scheidet also
aus. Die Signaturen aus ADR-023 nützen erst etwas, wenn die VM sie vor dem
Start prüft (REQ-GIT-005).

**Entscheidung:**

1. **Auslöser:** Rollout manuell per SSH: `normly-deploy deploy vX.Y.Z`. Das
   Skript ist timerfähig gehalten, einen Timer gibt es nicht.
2. **Prüfung vor dem Start:** `cosign verify` aller fünf Images gegen die
   Identität `images.yml@refs/tags/vX.Y.Z` des Release-Workflows. Compose-Datei
   und Skript-Assets reisen im signierten `pipeline`-Image und werden aus dem
   geprüften `pipeline@<digest>` entnommen. Die geprüften Digests werden
   festgehalten (Digest-Pinning); nach `compose pull` müssen die gezogenen
   Digests den geprüften entsprechen, sonst startet nichts.
3. **Ablauf:** aktuellen Tag und Wissensbestand-Version lesen,
   Pre-Rollout-Sicherung (ohne bestätigten Upload kein Rollout), `pull`,
   `up -d --wait`. Der aktuelle Tag wird abgelehnt; solange ein
   fehlgeschlagener Rollout vermerkt ist (`state/failed_rollout`), startet
   kein neuer `deploy` (bewusstes Übergehen: die Markierungsdatei entfernen).
   Es gibt keinen automatischen Rückweg.
4. **Rollback stellt Images und Daten auf den Stand vor dem Rollout zurück.**
   Weil Alembic-Migrationen nur vorwärts laufen, wird das Schema neu
   aufgebaut: Dienste stoppen, alle Tabellen des Schemas `public` verwerfen
   (Liste aus der Datenbank, das Schema bleibt, damit pgvector erhalten
   bleibt), `migrate` mit dem vorherigen Image, Wissensbestand in der
   damals aktiven Dump-Version importieren (vor den Nutzerdaten, wegen der
   Fremdschlüssel), die zurückgezogenen Kennungen der Sicherung
   (`exchange import-tombstones`, siehe ADR-026), Nutzerdaten mit
   `pg_restore --data-only`, vorheriges Release starten. Vorab prüft das
   Skript, dass die Alembic-Revision der Sicherung dem Alembic-Head des
   vorherigen Images entspricht, dass der aufgezeichnete Wissensbestand-Dump
   abrufbar und prüfbar ist (Signatur, Modell, Prüfsummen; ohne nutzbaren
   öffentlichen Schlüssel Abbruch, bevor etwas verändert wird) und dass die
   Tombstone-Datei der Sicherung abrufbar, entschlüsselbar und gültig ist
   (eine Sicherung, deren `meta.json` die Datei zusagt, der sie aber fehlt,
   gilt als beschädigt: Abbruch; eine ältere Sicherung ohne Zusage führt zu
   einer Warnung, der Rollback läuft weiter), und verlangt
   die Eingabe des Ziel-Tags (oder `--yes`). Der private Schlüssel wird nur
   für den Lauf bereitgestellt (`--age-identity FILE`). Scheitert der
   Rollback nach dem Verwerfen, gibt das Skript Hinweise zur Wiederherstellung;
   ein erneuter Aufruf ist gefahrlos.
5. **Sicherung:** die Nutzerdaten-Tabellen (`exchange tables user`) und, als
   zweite verschlüsselte Datei, die zurückgezogenen Kennungen
   (`<base>.tombstones.age`, ADR-026; nie Inhalt, Rechte oder Nutzerdaten).
   Beide `age`-verschlüsselt auf der VM mit dem öffentlichen Schlüssel, Upload
   per `rclone` in einen privaten STACKIT-Object-Storage-Bucket. Der private
   Schlüssel liegt nie auf der VM. Reihenfolge des Uploads: `meta.json`,
   `dump.age`, `tombstones.age`, `.sha256`; die Prüfsumme deckt beide
   verschlüsselten Dateien ab und ist die Commit-Markierung, erst mit ihr
   zählt eine Sicherung. `meta.json` trägt `"tombstones": true`.
6. **Aufbewahrung:** 7 tägliche, 2 monatliche (jeweils der neueste tägliche
   Stand der beiden jüngsten Kalendermonate), 3 Pre-Rollout-Stände. Die
   Aufbewahrung gilt für beide Dateien einer Sicherung: die Bereinigung löscht
   `.sha256`, `meta.json`, `tombstones.age`, `dump.age` in dieser Reihenfolge
   und überspringt Objekte, die nicht im Bucket liegen (ältere Sicherungen
   ohne Tombstone-Datei). Sie zählt nur committete Sicherungen und löscht
   Waisen (ohne `.sha256`, auch eine einzelne `tombstones.age`) erst nach
   einem Tag. Zusätzlich bleibt die 30-Tage-Sicherung
   der Gesamtdatenbank durch Flex das Betriebsnetz.
7. **Restore-Test:** manuell und dokumentiert (`docs/guide/operations.md`),
   nach dem Bau einmal, danach monatliche Erinnerung.

**Begründung:**

- *Manueller Auslöser:* Ein Mensch entscheidet über das Migrationsfenster.
  Migrationen liefen sonst unbeaufsichtigt, und ein Timer bräuchte eine
  „höchster Tag“-Logik und ein Stabilitätsfenster.
- *Rollback = Neuaufbau:* Migrationen sind nur vorwärts. Ein reiner
  Image-Rollback verlangte eine Expand/Contract-Disziplin, die es nicht gibt;
  ein reiner Datenrestore ließe das neue Schema stehen.
- *Nur Nutzerdaten sichern:* Der Wissensbestand ist über den Dump
  (ADR-025) reproduzierbar; ein täglicher Gesamtdump wäre bei zweistelligen GB
  verschwendet, die Nutzerdaten sind dagegen klein und unersetzlich.
- *Schlüsseltrennung:* Die VM kann Sicherungen schreiben, aber nicht
  entschlüsseln (der Bucket-Zugang der VM umfasst Lesen, weil der Rollback
  die Sicherung herunterlädt; der private Schlüssel fehlt).
  Auch bei kompromittierter VM bleiben die Sicherungen geschützt, anders als
  bei serverseitiger Verschlüsselung, deren Schlüssel beim Anbieter neben den
  Daten liegt (CLAUDE.md: Schlüssel nie neben den Daten).
- *Digest-Pinning:* `cosign verify` prüft, worauf das Tag in diesem Moment
  zeigt. Ein zwischen Prüfung und `pull` umgesetztes Tag würde sonst die
  Prüfung umgehen.
- *Commit-Markierung:* Ein abgebrochener Upload darf weder als Sicherung
  zählen noch eine ältere, gültige verdrängen.

**Verworfen:** Timer mit Auto-Rollout; reiner Image-Rollback mit
Expand/Contract-Disziplin; ausschließlich serverseitige Verschlüsselung;
täglicher Gesamtdump; nur Pre-Rollout-Dumps; wöchentliche Stände (Nutzen
jenseits von 7 Tagen klein).

**Folgen:**

- Ein Rollback verwirft alle Änderungen seit der Pre-Rollout-Sicherung
  (Konten, Chats, Watchlists). Das Skript warnt und verlangt Bestätigung.
- Die Rollback-Dauer wächst mit dem Wissensbestand (Neu-Import).
- Voraussetzung: Der Wissensbestand in Produktion ändert sich nur durch
  Dump-Import, nie durch Ingestion auf der VM (zugleich Voraussetzung für die
  Verkleinerung der VM, TP1a).
- `pg_dump`, `psql` und `pg_restore` laufen auf dem Host; `NORMLY_DATABASE_URL`
  muss dort auflösbar sein (verwaltete Datenbank, nicht das gebündelte Profil).
  Das Datenbankpasswort steht in den Prozessargumenten (Annahme: Einzelmandant-VM;
  Härtung zurückgestellt). Es braucht Docker Compose ab 2.20 (`--wait-timeout`).
- Offen: Kryptographisches Löschen bei Vertragsende (ADR-014) für lizenzierte
  Bestände ist Aufgabe der kommerziellen Schicht; sie müssen von Sicherungen
  ausgenommen oder je Herausgeber verschlüsselt werden. Der Secrets-Fluss per
  AppRole (TP3) liegt außerhalb. PITR und Verschlüsselung der Flex-Sicherungen
  sind zu klären. **Objektsperre (Entscheidung 2026-10-10): vorerst keine.**
  STACKIT bietet Object Lock nach Angabe des Betreibers nur nach einem
  projektweiten Compliance Lock und nur beim Anlegen des Buckets;
  unumkehrbar (vor Umsetzung gegen die STACKIT-Doku zu prüfen). Dagegen
  sprechen: Unumkehrbarkeit vor der ersten Live-Abnahme, Wirkung auf das ganze
  Projekt, Konflikt mit der eigenen Aufbewahrung (`normly-backup` löscht alte
  Stände) und der Zusage, gelöschte Nutzerdaten nicht wiederkehren zu lassen
  (Rollback spielt Löschungen der letzten 90 Tage nach; eine längere Sperre
  hielte sie länger vor). Akzeptiertes Restrisiko: Mit gestohlenen Zugangsdaten
  der VM ließen sich Sicherungen löschen; gelesen werden können sie nicht
  (`age`, privater Schlüssel außerhalb). Minderung zu prüfen: eigene
  Zugangsdaten der VM ohne Löschrecht. Neubewertung nach der Live-Abnahme; ein
  späterer zweiter Bucket mit Sperre und Frist von höchstens 90 Tagen wäre
  möglich. Das Zusammenspiel
  von `docker compose up --wait` mit dem einmaligen `migrate`-Dienst und die
  Abfrage des Alembic-Heads sind bislang nur gegen Attrappen geprüft, bis
  zur Live-Abnahme.

Details: `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md`,
Betrieb: `docs/guide/operations.md`.

---

## ADR-025 — Wissensbestand-Dump als Austauschformat

**Status:** beschlossen (2026-10-09); ergänzt ADR-010, ändert die Aussage zur
Wissensbasis in ADR-021 (siehe Nachtrag dort)

**Kontext:** ADR-010 trennt Code und Daten, REQ-DIST-004 verlangt einen
eigenständig versionierten Dump, der beim ersten Start bezogen wird. Bisher
entsteht der Wissensbestand per Ingestion auf der VM; weder Selbsthoster noch
ein Rollback können ihn reproduzieren.

**Entscheidung:**

1. **Format:** Parquet je Tabelle plus `manifest.json` und die Ed25519-Signatur
   `manifest.json.sig`. Das Manifest führt Austauschschema-Version
   (unabhängig von Alembic), Dump-Version und Zeitpunkt, Einbettungsmodell mit
   Name und gepinnter Revision, Vektordimension (1024), Quelllieferungen und
   Prüfsumme samt Zeilenzahl je Datei.
2. **Zugriff:** Export und Import laufen über die Repository-Schicht
   (`KnowledgeExchangeRepository`), nicht über Postgres-Werkzeuge.
3. **Signatur:** Ed25519 in Python (`cryptography`), im Kern geprüft. Der
   öffentliche Schlüssel liegt im Repository. Die Schlüsselzeremonie steht noch
   aus; bis dahin muss der Schlüssel angegeben werden. Er wird in dieser
   Reihenfolge aufgelöst: `--public-key`, Umgebungsvariable
   `NORMLY_KB_PUBLIC_KEY_FILE`, mitgepackter Schlüssel.
4. **Verteilung:** öffentlich lesbarer STACKIT-Object-Storage-Bucket mit
   Kalenderversion `kb/<version>/` und `kb/latest`. Eine Version ist
   unveränderlich. `fetch` lädt nur von `NORMLY_KB_BASE_URL` (https, für
   localhost auch http) und prüft Version und Pfade.
5. **Import:** atomar und idempotent; der Aufrufer committet, die
   importierte Version wird in der Datenbank festgehalten. Was die neue Version
   nicht mehr enthält, wird nach ADR-026 behandelt, nie blockiert durch
   Nutzerdaten: Zitate lösen, Inhalt löschen, Tombstones setzen, Lieferungen
   zurückziehen, dann einfügen oder aktualisieren. Ein Dump ohne Dokumente
   wird abgelehnt, solange die Datenbank Dokumente hält, es sei denn
   `--allow-empty` ist gesetzt.
6. **Prüfungen beim Import:** Signatur, Austauschschema-Version, Modellname
   **und** Modellrevision (`NORMLY_EMBEDDING_MODEL_REVISION`), Dimension,
   Prüfsummen. Bei Abweichung Abbruch, keine stillen falschen Einbettungen.
   Dieselben Prüfungen laufen ohne Datenbank als Unterbefehl `verify
   (--from DIR | --fetch VERSION)`; der Rollback ruft ihn vor dem ersten
   destruktiven Schritt auf, damit ein nicht prüfbarer Dump nicht erst nach
   dem Verwerfen der Tabellen auffällt.
7. **Export-Gate:** die Rechteklassifikation als einziges Tor, über alle
   Rechtsräume hinweg ausgewertet. Exportiert wird, was eine nicht
   widerrufene Klassifikation mit `may_process` und `may_export_free` hat,
   dessen Lieferung nicht zurückgezogen ist und dessen Quelle Kategorie A, B
   oder D hat und kein kommerziell verwerteter Katalog ist. Fehlende
   Klassifikation heißt nicht exportieren. Zusammengeführte Werke werden samt
   Ziel exportiert, damit die Weiterleitung erhalten bleibt. Nutzerdaten und
   lizenzierte Bestände sind nie enthalten.
8. **Erster Start:** der Compose-Dienst `kb-import` (Profil `tools`) führt
   `import --fetch latest` aus.

**Begründung:**

- *Parquet statt `pg_dump` (Nutzerentscheidung, gegen die ursprüngliche
  Empfehlung):* ADR-006 und CLAUDE.md verlangen Datenbankzugriff nur über die
  Repository-Schicht, damit die Speichertechnologie austauschbar bleibt;
  `pg_dump` ist ein Postgres-Artefakt und umgeht sie.
- *Öffentliches Produkt (REQ-DIST-004):* Ein Format ohne Bindung an unsere
  Alembic-Revision überlebt Schemaänderungen. Bei `pg_dump` müsste jeder
  Selbsthoster die passende Anwendungsversion finden.
- *Abstammung:* Ein tabellenweiser Export mit Quelllieferung je Zeile hält die
  Rücknahme einer Lieferung auch im Dump nachvollziehbar.
- *Parquet statt NDJSON:* Einbettungen (1024 Floats, etwa 4 KB je Abschnitt)
  wären sonst unhandlich.
- *Preis:* mehr Code (Export, Import, Austauschschema), langsamerer Import,
  Idempotenz selbst herzustellen. Das nehmen wir in Kauf.
- *Ed25519 im Kern statt cosign/minisign:* Der Import läuft im
  `pipeline`-Image und beim Selbsthoster; ein zusätzliches Binary vergrößerte
  das Image und schüfe eine zweite Installationshürde. Keyless-Signatur geht
  nicht, weil der Dump lokal entsteht, nicht in der CI.
- *Object Storage statt Git:* große Binärdateien und anonymer Zugriff sind in
  einem Git-Repository unhandlich; die Wissensbasis bleibt damit auf STACKIT
  (CLAUDE.md).
- *Import mit Tombstones statt Blockieren:* siehe ADR-026.

**Verworfen:** `pg_dump` des Wissensbestands; Delta-Dumps (das Format lässt
sie offen, gebaut werden sie nicht); STACKIT Git als Ablage; ein zusätzliches
Git-Manifest als Verlauf (zweites System); NDJSON.

**Folgen:**

- ADR-021 erhält einen Nachtrag; CLAUDE.md und REQ-GIT-005 sind angepasst.
- `docs/guide/self-hosting.md` beschreibt den Import, `docs/guide/operations.md`
  Export, Signatur und Veröffentlichung.
- Das Export-Gate liest die Rechteklassifikation und führt keinen zweiten
  Prüfpfad ein.

**Personennamen (entschieden 2026-10-09):** Der Export ersetzt Personennamen
durch die Rolle `normly maintainers`. Betroffen sind
`source.responsible_person` und `rights_classification.classified_by`; beide
Spalten tragen in jeder exportierten Zeile die Konstante `PUBLISHED_ROLE`. Die
Ersetzung geschieht im Export-Statement der Repository-Schicht, also an der
Stelle des Export-Gates, und ändert weder Manifest noch Austauschschema (keine
Versionserhöhung). Der Dump trägt nie einen Namen; die Quellenregistrierung im Code enthält nur
einen Platzhalter, und Namen, die ein Ingestion-Betreiber einträgt, liegen nur
in dessen eigener Datenbank. Ein Import überschreibt die beiden Spalten mit dem
Rollenlabel: Produktion, die den öffentlichen Dump einspielt, trägt daher das
Label, nie Namen; ein erneuter Export eines importierten Stands ist zeilengleich.
Einen Dump nie in die Ingestion-Datenbank importieren: der Upsert überschreibt
dort die Namen unwiderruflich. Maskiert wird auch
`classified_by="pipeline:automatic"`; der öffentliche Dump unterscheidet damit
nicht zwischen automatischer und menschlicher Klassifikation (bewusster
Kompromiss, das Label ist eine Rolle und keine Aussage über menschliche
Prüfung).
Ein Test sucht einen eindeutigen Namen in allen Zeilen, allen Parquet-Dateien
und im Manifest.

**Offene Punkte:**

- **Delta-Dumps** sind nicht gebaut.
- **Schlüsselzeremonie:** Erzeugung, Verwahrung und Veröffentlichung des
  Signaturschlüssels stehen aus.

Details: `docs/superpowers/specs/2026-10-09-tp4-deployment-automation-design.md`.

---

## ADR-026 — Umgang mit Nutzerdaten beim Wissensbestand-Import

**Status:** beschlossen (2026-10-09); ersetzt die Blockierregel des Imports
aus ADR-025

**Kontext:** Der Import eines Wissensbestand-Dumps brach mit
`ImportBlockedError` ab, sobald Nutzerdaten (`watchlist`, `notification`,
`notified_edge`, `chat_message_citation`) auf eine Zeile verwiesen, die der neue
Dump nicht mehr enthält. Für eine rechtlich gebotene Rücknahme (Lieferung
zurückgezogen, Klassifikation widerrufen) ist das falsch: Sie darf nicht an
Nutzerdaten scheitern (CLAUDE.md, „Abstammung mitführen“). Befund aus dem Code:
Keine Nutzerdaten-Tabelle speichert urheberrechtlich geschützten Inhalt, es
sind nur Verweise (`work_id`, `edge_id`, `document_id`, `segment_id`); der Text
eines Zitats wird erst beim Lesen aus `segment` geholt.

**Entscheidung:** Eine Rücknahme gewinnt immer; ein Nutzerverweis blockiert nie
einen Import. Was der Dump nicht mehr enthält, wird nach Klasse behandelt:

| Klasse | Tabellen | Behandlung |
|---|---|---|
| Tombstone (Kennung, kein Inhalt) | `work`, `document`, `edge` | Zeile bleibt, `retired_at` wird gesetzt; Kanten werden zusätzlich widerrufen (`revoked_at`). Nutzerverweise bleiben gültig. |
| Herkunft | `source`, `delivery` | Werden nie gelöscht; eine fehlende Lieferung erhält `withdrawn_at`. |
| Inhalt/Ableitung | `document_designation`, `document_title`, `rights_classification`, `segment`, `embedding`, `document_embedding` | Werden physisch gelöscht. |

Ablauf in `replace_knowledge_base`, in dieser Reihenfolge: Schlüssel des Dumps
laden; Zitate lösen (`chat_message_citation.segment_id` wird `NULL` für Segmente,
die der Dump nicht enthält); fehlenden Inhalt in umgekehrter
Fremdschlüssel-Reihenfolge löschen; fehlende Tombstones zurückziehen; fehlende
Lieferungen mit `withdrawn_at` versehen; den Dump einfügen oder aktualisieren
(Zeilen der Tombstone-Klassen aus dem Dump erhalten `retired_at = NULL`:
Wiederkehr); Importvermerk schreiben. Löschen und Zurückziehen laufen **vor**
dem Einfügen, damit eine Neulieferung mit neuen IDs nicht an natürlichen
Eindeutigkeitsschlüsseln kollidiert (Bezeichner, Titel, partieller Index aktiver
Kanten). `ImportBlockedError` (mit `.step`) bleibt nur als letzte Sicherung für
einen unerwarteten Fremdschlüssel.

- `retired_at` (Migration 0033; `work`, `document`, `edge`) ist keine
  Austauschspalte: Dumpformat und `EXCHANGE_SCHEMA_VERSION` bleiben unverändert.
- `retired_at` ist keine Filterpflicht. Ein zurückgezogenes Dokument hat keine
  Rechteklassifikation mehr; jede tor-gebundene Lesestelle (das einzige Tor)
  schließt es damit aus. Es entsteht kein zweiter Prüfpfad.
- Schutz vor leerem Dump: Ein Dump ohne Dokumente wird abgelehnt, solange die
  Datenbank Dokumente hält (`allow_empty` bzw. `--allow-empty` hebt das auf).
- Ein Test geht alle Fremdschlüssel jeder Tabelle außerhalb des Wissensbestands
  auf den Wissensbestand durch (fail-closed), nicht nur die der
  Nutzerdaten-Tabellen, also auch `identity_resolution_case`: Jedes Ziel muss
  zu einer Klasse gehören oder eine ausdrückliche Löseregel haben.
- Meldung: Ein Widerruf löscht in Produktion die Klassifikation, der
  Rechteänderungs-Pfad von `notify-watchers` sähe also nichts. Neuer
  Benachrichtigungstyp `no_longer_available` (Migration 0034, Tabelle
  `notified_retirement`, `trigger_type` auf VARCHAR(19)): `notify-watchers`
  erzeugt eine Meldung je zurückgezogenem Dokument eines beobachteten Werks, nur
  für Rücknahmen nach Beginn der Beobachtung; Dedup-Schlüssel enthält
  `retired_at` (eine erneute Rücknahme nach Wiederkehr wird neu gemeldet). Kein
  Link; E-Mail-Betreff „Ein beobachtetes Regelwerk ist nicht mehr verfügbar“;
  Glocke „Nicht mehr verfügbar“ / „No longer available“. `delete_account`
  entfernt die `notified_retirement`-Zeilen des Kontos.

**Begründung:** Die zugesagte Rücknahme darf nie von einem Menschen oder von
Nutzerdaten abhängen. Gelöschter Inhalt ist auch in Produktion und nach Ablauf
der Sicherungen nicht mehr lesbar; Tombstones tragen nur Kennungen. Kein
Nutzerverweis geht verloren, weil sich der Wissensbestand ändert.

**Verworfen:**

- Blockieren mit Bereinigungswerkzeug: Die Rücknahme wartete auf einen Menschen.
- Nutzerverweise anpassen oder löschen: Datenverlust ohne Nutzen, da nur
  Verweise betroffen sind.
- Reine Tombstones auch für Inhalt: Die Rücknahme wäre nur logisch, der Text
  bliebe in Datenbank und Sicherungen lesbar.
- Bezeichner und Titel als Teil des Tombstones: Sie kollidieren bei einer
  Neulieferung mit den natürlichen Eindeutigkeitsschlüsseln (Befund im Review);
  das Dokument behält Herausgeber, Nummer, Ausgabe und Teil als Kennung.

**Rollback und Sicherung (Erweiterung 2):** `normly-deploy rollback` (ADR-024)
baut die Datenbank neu auf und importiert die ältere Dump-Version. Tombstones
stehen in keinem Dump; Nutzerzeilen, die auf sie zeigen, verletzten beim
Einspielen den Fremdschlüssel. Deshalb enthält jede Sicherung eine zweite,
`age`-verschlüsselte Datei `<base>.tombstones.age`:

- *Inhalt:* JSON (`format` 1, `created_at`, `rows` je Tabelle in
  Fremdschlüssel-Reihenfolge) mit allen Zeilen aus `work`, `document` und
  `edge`, deren `retired_at` gesetzt ist, plus dem Abschluss über die
  Fremdschlüssel-Eltern innerhalb von `source`, `delivery`, `work`, `document`,
  `edge`. Der Abschluss wird aus den ORM-Fremdschlüsseln berechnet, nicht
  hartverdrahtet, und nimmt nur Eltern auf, nie Kinder. Alle Spalten, auch
  `retired_at` und `revoked_at`. Nie Inhalt, Rechte oder Nutzerdaten.
  `source.responsible_person` kann enthalten sein; in Produktion ist es die
  veröffentlichte Rollenbezeichnung (Importe überschreiben es), ein Klarname
  nur in einer Datei aus einer Ingestion-Datenbank. Er liegt nur in der
  verschlüsselten Sicherung.
- *Erzeugung und Prüfung:* im Container (`exchange export-tombstones`, stdout),
  auf dem Host vor dem Verschlüsseln geprüft (JSON-Objekt, `format` 1, `rows`
  mit genau den fünf Tabellen, je eine Liste). Eine ungültige Ausgabe bricht
  die Sicherung ab.
- *Einspielen:* im Rollback nach dem Wissensbestand-Import und **vor**
  `pg_restore` (`exchange import-tombstones`, JSON auf stdin, im Image des
  vorherigen Release). Einfügen in Fremdschlüssel-Reihenfolge mit
  `ON CONFLICT DO NOTHING`; vorhandene Zeilen bleiben unverändert;
  `work.merged_into_work_id` wird aufgeschoben. Eingefügte Zeilen aus `work`,
  `document`, `edge` erhalten `retired_at` (gesicherter Wert, bei lebenden
  Eltern `created_at` der Datei) und gelten damit als zurückgezogen. Sie haben
  keine Klassifikation, jede tor-gebundene Lesestelle schließt sie aus. Ein
  späterer normaler Import, der die Zeile enthält, setzt `retired_at` wieder
  auf `NULL`.
- *Vorabprüfung:* Der Rollback lädt, entschlüsselt und prüft die
  Tombstone-Datei vor dem Banner, den Dump nach der Bestätigung und vor dem
  Stopp; vor dem Löschen ist beides vorhanden und entschlüsselt. Sagt
  `meta.json` `"tombstones": true`, fehlt aber die Datei, gilt die Sicherung als
  beschädigt (Abbruch). Eine ältere Sicherung ohne Zusage bleibt nutzbar: Der
  Rollback warnt deutlich (ein Fremdschlüsselfehler ist möglich, wenn
  Nutzerdaten auf zurückgezogene Dokumente zeigen) und läuft weiter.
- *Nicht wiederhergestellt:* Inhalt und Rechte zurückgezogener Dokumente; nur
  Kennungen. Das ist gewollt, die Rücknahme bleibt wirksam.
- *`revoked_at`:* An einer zurückgezogenen Kante ist `revoked_at` der
  **Importzeitpunkt**, nicht der Zeitpunkt des Widerrufs beim Produzenten. Es
  ist kein Ereignisdatum und so nicht zu lesen.

**Folgen / offen:**

- Ein Tombstone behält nur `origin_issuer`, `origin_number`, `edition` und
  `part`. Jede Oberfläche, die Tombstones auflistet, muss darauf zurückfallen.
- Die Ingestion legt bei Neulieferung nach einem Widerruf einen **neuen**
  Dokumentknoten an (Bezeichner sind gelöscht, `find_by_designation` findet
  nichts). Beobachtungen und Meldungen bleiben am Tombstone und gehen nicht auf
  den neuen Knoten über. Produkt- und Identitätsentscheidung, offen.
- Das Export-Gate des Produzenten lässt ein Dokument aus, dessen erzeugende
  Lieferung widerrufen wurde, auch nach einer Neulieferung. Offen.
- Dumps müssen aus einer Abstammungslinie mit stabilen IDs stammen. Eine neu
  aufgebaute Produzenten-Datenbank mit neuen IDs kann mit stehengebliebenen
  Tombstones kollidieren (partieller Index aktiver Kanten u. a.) und endet in
  `ImportBlockedError`.
- Aufbewahrung und Alterung von Tombstones sind offen (auch nach ADR-027).
- Die Rechteänderungs-Meldung (`RIGHTS_CHANGE`) für reine Änderungen von
  Rechtewerten, ohne dass das Dokument verschwindet, entsteht weiter beim
  Produzenten, nicht in Produktion.
- Der Schutz vor leerem Dump vertraut den Zeilenzahlen des Manifests; das
  Manifest ist signiert.

Details: `docs/superpowers/specs/2026-10-09-user-data-on-kb-import-design.md`.

---

## ADR-027 — Lebenszyklus der Nutzerdaten

**Status:** beschlossen (2026-10-10); baut auf ADR-014, ADR-017, ADR-024 und
ADR-026

**Kontext:** Personenbezogene Daten sollen nur gespeichert werden, wenn ein
Konto sie braucht, und nur so lange, wie der Zweck besteht; Betroffene sollen
ihre Daten einsehen und löschen können, und eine Löschung soll eine
Wiederherstellung aus Sicherungen überstehen. Die Bestandsaufnahme vom
2026-10-10 zeigte Lücken:

- Anonyme Chats wurden gespeichert (`chat_session`/`chat_message`, Cookie
  `normly_session` mit 90 Tagen Laufzeit) und nie gelöscht, obwohl der Server
  sie zum Antworten nicht braucht: Jede Frage wird einzeln beantwortet.
- `account_session` und `account_token` wurden nie gelöscht (die Ablaufzeit
  wurde nur geprüft); verlassene Registrierungen blieben ewig; ungelesene
  Benachrichtigungen ebenso.
- Es gab keinen Weg, einzelne Chat-Verläufe zu löschen.
- Der Rollback (ADR-024) stellt Nutzerdaten vom Sicherungszeitpunkt wieder her:
  zwischenzeitlich gelöschte Konten und Verläufe tauchten wieder auf.
- Der Export (`GET /v1/accounts/export`) war unvollständig: Die
  Beobachtungsliste nannte nur `work_id`, Zitate fehlten, und der
  Chat-Sitzungs-Token (ein Geheimnis) stand im Export.

**Entscheidung:**

*Grundsatz.* Gespeichert wird nur, was ein Konto braucht. Fristen stehen als
benannte Konstanten an einer Stelle (`core/src/normly_core/retention.py`) und
werden von einem idempotenten Aufräumbefehl durchgesetzt.

*Anonymer Chat ohne Speicherung.* `POST /v1/chat` ohne gültige Konto-Identität
schreibt nichts in die Datenbank und antwortet mit `session_token: null`. Ein
Chat-Token ohne gültiges Konto wird ignoriert. Das Frontend setzt für anonyme
Nutzung kein Chat-Cookie und entfernt ein vorhandenes; die Unterhaltung lebt
nur im Browser-Tab. Die Verknüpfung „anonyme Sitzung beim Anmelden ans Konto
hängen“ entfällt bewusst. Das Kontingent bleibt davon unberührt: Es wird
serverseitig über die Ratenbegrenzung gezählt (Cookie `normly_anon_id` plus
Herkunftsadresse, `rate_limit_bucket`), nicht über Chat-Sitzungen
(REQ-ACC-003). Vorhandene anonyme Verläufe (`account_id` leer) löscht der
Aufräumbefehl.

*Chats mit Konto* bleiben bis zur Löschung durch die Person oder durch die
Kontolöschung. `DELETE /v1/chat/sessions/{id}` löscht einen eigenen Verlauf
(204; 404 bei fremder oder unbekannter ID; 401 ohne Anmeldung),
`DELETE /v1/chat/sessions` alle eigenen (`{"deleted": n}`); die Seitenleiste
bietet beides mit Bestätigung.

*Datenverzeichnis.* Alle Tabellen der Nutzerdaten-Gruppe (`USER_TABLES`):

| Tabelle | Zweck | Personenbezug | Frist | Löschweg |
|---|---|---|---|---|
| `account` | Konto, Anmeldung | E-Mail, Name, Passwort-Hash, Avatar | bis zur Kontolöschung; **verlassene Registrierung** (E-Mail nie bestätigt, älter als 30 Tage, ohne Google-Verknüpfung, ohne irgendeine Konto-Sitzung) 14 Tage nach zugestellter Vorwarn-E-Mail, nie ohne diese | Kontolöschung durch die Person (kaskadiert auf alle Tabellen mit Kontobezug); Aufräumbefehl |
| `account_session` | angemeldete Sitzung | Kontobezug, Sitzungs-Token; keine IP, kein User-Agent | 7 Tage nach Ablauf | Aufräumbefehl; Kontolöschung |
| `account_google_identity` | Verknüpfung mit Google-Anmeldung | Google-Kennung, Kontobezug | bis zur Kontolöschung | Kontolöschung |
| `account_token` | Einmal-Token (Bestätigung, Zurücksetzen, Magic Link) | Kontobezug | 24 Stunden nach Ablauf oder Verwendung | Aufräumbefehl; Kontolöschung |
| `oauth_state` | CSRF-Schutz der Google-Anmeldung | keiner (Zufallswert) | unverändert (1 Stunde) | bestehende Bereinigung |
| `watchlist` | Beobachtungsliste | Kontobezug, Interessen | bis zur Kontolöschung oder Entfernen durch die Person | Person; Kontolöschung |
| `notification` | Meldungen | Kontobezug, beobachtetes Werk | gelesen 60 Tage, ungelesen 365 Tage nach Anlage | Aufräumbefehl; Kontolöschung |
| `notified_edge`, `notified_retirement`, `rights_notification_baseline` | Buchführung gegen Doppelmeldungen | Kontobezug | bis zur Kontolöschung | Kontolöschung |
| `chat_session`, `chat_message`, `chat_message_citation` | Chat-Verläufe mit Konto | Fragen und Antworten der Person | keine Frist; anonyme Altzeilen (`account_id` leer) werden gelöscht | Person (pro Verlauf oder alle); Kontolöschung; Aufräumbefehl für Altbestand |
| `rate_limit_bucket` | Ratenbegrenzung und Kontingent | pseudonymer Schlüssel aus Browser-Kennung und Herkunftsadresse | unverändert (10 Minuten) | bestehende Bereinigung |
| `deletion_log` | Löschprotokoll (siehe unten) | keine: nur Art, Kennung, Zeitpunkt | 90 Tage | Aufräumbefehl |

Der Avatar liegt in `account` und verschwindet mit dem Konto oder beim
Entfernen. Das Datenverzeichnis ist neu zu bewerten, sobald `account_session`
IP-Adressen oder User-Agent speichert (heute nicht der Fall).

*Verlassene Registrierungen.* Die Regel ist bewusst enger als „unbestätigt“:
Google-Konten werden nie als bestätigt markiert (`email_verified_at` bleibt
leer), und Konten mit Passwort können sich auch ohne Bestätigung anmelden. Ein
Konto in Benutzung hat daher eine Google-Verknüpfung oder mindestens eine
`account_session`-Zeile (auch eine abgelaufene, solange sie nicht gelöscht
ist; die Löschfrist der Sitzung beginnt erst 7 Tage nach Ablauf) oder eine
Anmeldung innerhalb der letzten 30 Tage: `account.last_login_at` wird bei jeder
Sitzungsanlage gesetzt und überlebt im Gegensatz zur Sitzungszeile die
Abmeldung. Nur ein Konto ohne all das, nie bestätigt und älter als 30 Tage,
gilt als verlassen. Das
trifft auch ein Passwort-Konto, das benutzt und dann lange pausiert wurde,
sobald seine Sitzungen entfernt sind; deshalb wird kein Konto still gelöscht:
Der Aufräumbefehl schickt zuerst eine zweisprachige Vorwarn-E-Mail (Datum der
Löschung, Anmelde-URL aus `NORMLY_PUBLIC_BASE_URL`, kein Token) und setzt
erst nach erfolgreichem Versand `account.deletion_warned_at`. Gelöscht wird
frühestens 14 Tage danach (strikt), und nur wenn das Konto dann noch alle
Bedingungen erfüllt. Anmeldung, Bestätigung oder Google-Verknüpfung machen das
Konto wieder „nicht verlassen“; der nächste Lauf setzt die Warnung zurück.
Voraussetzung ist ein SMTP-Relay (`NORMLY_SMTP_*`): Ohne Relay oder bei
fehlgeschlagenem Versand wird nie gewarnt und damit nie gelöscht; der Versand
wird im nächsten Lauf erneut versucht. Ein Konto wird nie im selben Lauf
gewarnt und gelöscht (Reihenfolge: zurücksetzen, löschen, warnen). Der
Löschlauf sperrt die Kandidaten und prüft die Bedingung samt Warnzeitpunkt
erneut, damit eine gleichzeitige Bestätigung, Anmeldung oder
Google-Verknüpfung nicht verloren geht. `deletion_warned_at` und
`last_login_at` werden nicht exportiert. Die Mail nennt das Datum als
„frühestens am“, weil der tägliche Lauf den Zeitpunkt um bis zu einen Tag
verschieben kann.

*Aufräumbefehl.* `python -m normly_core.pipeline cleanup-user-data` setzt alle
Fristen der Tabelle durch (Sitzungen, Tokens, verlassene Registrierungen,
gelesene und ungelesene Benachrichtigungen, anonyme Chat-Altbestände,
Löschprotokoll), ist idempotent und gibt nur Zähler aus. Der systemd-Timer
`normly-cleanup` (täglich 04:00 UTC) startet über `scripts/normly-cleanup`; das
Skript überspringt den Lauf mit Exitcode 0, solange `state/deploy.lock`
existiert. `cleanup-notifications` bleibt als Befehl bestehen.

*Export (Auskunft).* `GET /v1/accounts/export` liefert synchron als JSON:
Profil, Avatar (Data-URL), Beobachtungsliste mit lesbaren Dokumentkennungen
(alle Dokumente des Werks, auch zurückgezogene), Benachrichtigungen und Chats
mit Antworttyp und Zitaten (lesbare Dokumentkennung und Segment-ID). Nicht
enthalten: `session_token` (stattdessen die Sitzungs-ID), Passwort-Hash,
Tokens und Buchführung.

*Löschprotokoll und Wiederholung.* Tabelle `deletion_log(kind, entity_id,
deleted_at)` (`kind` ist `account` oder `chat_session`; Migration 0035). Der
Eintrag entsteht in derselben Transaktion wie jede Löschung (Kontolöschung,
Verlauf löschen, Aufräumen verlassener Registrierungen), enthält keine
personenbezogenen Daten, ist Teil der Nutzerdaten-Sicherung und wird nach
90 Tagen bereinigt (siehe Folgen). Der Kern bietet
`python -m normly_core.exchange export-deletions --since <ISO-8601>` (JSON auf
stdout) und `replay-deletions` (JSON auf stdin; wendet die Löschungen über die
normalen Löschfunktionen erneut an, idempotent, schon fehlende Einträge werden
trotzdem ins Protokoll geschrieben); `replay-deletions --check` meldet ohne
Datenbank, ob das Image den Befehl kennt.

Im Rollback (ADR-024): Das Skript liest die Löschungen seit dem
Sicherungszeitpunkt **minus eine Stunde** direkt aus der Datenbank (Host-`psql`
und `python3`, kein startbares Release-Image nötig; der Kernbefehl bleibt für den
manuellen Gebrauch) (Sicherheitsrand im Skript; eine doppelt angewendete Löschung
ist harmlos, weil UUIDs nie wiederverwendet werden). Dieser erste Export speist
Banner und die Entscheidung über `replay-deletions --check` im Image des
**vorherigen** Release (Exitcode 2 heißt „nicht unterstützt“, jeder andere
Fehler bricht ab). Nach dem Stopp der Dienste und vor dem DROP folgt ein zweiter
Export; dieses Dokument wird nach `pg_restore` und der Tombstone-Wiederherstellung
vom vorherigen Image angewendet. Schlägt der zweite Export fehl, bricht der
Rollback vor dem DROP ab (Datenbank unverändert, Hinweis zum Neustart). Vor dem
DROP wird die Liste nach `$STATE/rollback-deletions.json` (0600) geschrieben; ein
erneuter Lauf nach einem Fehler nach dem DROP führt sie mit dem frischen Export
zusammen (Vereinigung nach Art und Kennung, frühester Zeitpunkt) und löscht die
Datei erst, wenn das vorherige Release gesund läuft. `normly-cleanup` und
`normly-backup` laufen mit dem Tag aus `state/current_tag`, nie mit dem
Compose-Standard `edge`.
Eine fehlende Tabelle `deletion_log` (Release vor diesem Feature) gilt als leere
Liste. Kennt das vorherige Image den Befehl nicht, nennt das Banner Anzahl und
die ersten 20 `kind:id`; die vollständige Liste liegt in
`$STATE/rollback-pending-deletions.json` (0600) und muss von Hand erneut gelöscht
werden.

**Begründung:**

- Datensparsamkeit: Was der Server zum Antworten nicht braucht, wird nicht
  gespeichert. Das passt zu ADR-017 („ohne Konto entstehen keine
  personenbezogenen Daten“): Anonyme Nutzung bleibt vollständig, ohne dass der
  Verlauf anfällt.
- Kurze, benannte Fristen für technische Daten (Sitzungen, Tokens,
  Benachrichtigungen), keine Frist für Inhalte, die die Person selbst anlegt
  und jederzeit selbst löschen kann.
- Die Regel für verlassene Registrierungen löscht nie still: Ohne zugestellte
  Vorwarnung und 14 Tage Frist bleibt jedes Konto; ein falsch gelöschtes Konto
  wäre ein Datenverlust, ein zu spät gelöschtes nur ein gespeicherter
  Datensatz. Der Preis ist die Abhängigkeit von SMTP.
- Das Löschprotokoll enthält nur Kennungen. Es ist deshalb selbst keine
  Kopie der gelöschten Daten und kann als Teil der Nutzerdaten-Sicherung
  mitlaufen; ohne Kennung bliebe eine Löschung nach Rollback oder Restore
  unwirksam.
- Der Export bleibt synchron und lesbar (Kennungen statt interner IDs, wo
  möglich); ein Geheimnis wie der Chat-Token ist kein Datum der Person.

**Verworfen:**

- *Frist auch für Chats mit Konto:* Die Person legt sie selbst an, kann sie
  selbst löschen, und sie sind der Zweck des Kontos („Verläufe“, REQ-ACC-004).
  Eine stille Löschung wäre ein Funktionsverlust ohne Datenschutzgewinn.
- *Kurzfristige Speicherung anonymer Sitzungen:* Der Server braucht sie nicht;
  jede Speicherung wäre Daten ohne Zweck, und das Cookie bliebe nötig.
- *Kryptographisches Löschen je Konto in Sicherungen:* Ein Schlüssel je Konto
  im Sicherungsformat wäre eine große Änderung an Sicherung und Restore; das
  Löschprotokoll mit Replay erreicht für diesen Zweck dasselbe Ergebnis nach
  Wiederherstellung, und die Nachwirkung ist zeitlich begrenzt. (Für
  lizenzierte Bestände bleibt ADR-014 maßgeblich.)
- *Asynchroner Export per E-Mail-Link:* Mehr Infrastruktur (Warteschlange,
  Ablage, Link-Ablauf) und mehr gespeicherte Kopien, ohne dass der Umfang es
  verlangt.
- *Löschen aller unbestätigten Konten:* Google-Konten sind nie „bestätigt“ und
  Passwort-Konten können sich unbestätigt anmelden; die Regel würde
  Konten in Benutzung löschen.

**Folgen / offen:**

- *Nachwirkung in Sicherungen.* Eine Löschung wirkt in der Datenbank sofort, in
  Sicherungen erst, wenn sie auslaufen: Flex 30 Tage; eigene, `age`-verschlüsselte
  Sicherungen bis zu rund zwei Monate (7 tägliche, 2 monatliche Anker,
  3 Pre-Rollout-Sicherungen). Das Löschprotokoll sorgt dafür, dass Löschungen
  einen Rollback oder Restore überstehen. Es wird nach 90 Tagen bereinigt, länger als
  tägliche und monatliche Sicherungen halten. Eine Pre-Rollout-Sicherung kann
  älter werden, wenn lange kein Rollout folgt; wird aus einer Sicherung
  wiederhergestellt, die älter als 90 Tage ist, kann das Löschprotokoll die
  Löschungen aus der Zwischenzeit nicht mehr nachziehen.
- *Fachliche Prüfung.* Die Fristen sind Entscheidungen des Projekts und sollten
  von einer Fachperson für Datenschutz geprüft werden; dieses Dokument ist keine
  Rechtsberatung.
- Datenschutzerklärung und Verzeichnis der Verarbeitungstätigkeiten (Art. 30
  DSGVO) sind eigene Rechtstexte und nicht Teil dieser Arbeit.
- *Tombstones* (ADR-026): Aufbewahrung und Alterung bleiben offen.
- Ein vorheriges Release ohne `replay-deletions` braucht manuelles Nachlöschen
  (siehe oben); das gilt auch für den Restore-Test und die
  Notfall-Wiederherstellung aus Flex (Betriebsguide).
- Der Aufräum-Timer prüft `state/deploy.lock`, nimmt die Sperre aber nicht
  selbst. Bleibt eine verwaiste Sperre stehen, überspringt er täglich still.
- Löschen inaktiver Konten nach Frist mit Vorwarnung per E-Mail ist nicht
  umgesetzt.
- `account_session` speichert weder IP noch User-Agent; ändert sich das, sind
  Datenverzeichnis und Frist neu zu bewerten.
- Die Verknüpfung „anonym → Konto beim Anmelden“ entfällt; wer anonym gechattet
  hat, behält den Verlauf nur im geöffneten Tab.

Details: `docs/superpowers/specs/2026-10-10-user-data-lifecycle-design.md`,
Betrieb in `docs/guide/operations.md`.

---

## Offene Punkte

| Thema | Status | Nächster Schritt |
|---|---|---|
| Ausgründung GmbH | favorisiert, nicht beschlossen | Steuer- und vereinsrechtliche Prüfung vor Gründung |
| Rechtsform Trägerorganisation (e.V. / eG / Alternative) | offen | eG könnte Normungsorganisationen als Mitglieder statt Gegner einbinden |
| Rechteinhaber im Copyright-Header | offen | vor erstem externen Beitrag klären |
| Lizenzvertrag Trägerorganisation → GmbH | offen | muss zu marktüblichen Konditionen erfolgen, sonst Risiko für die Gemeinnützigkeit |
| RDF-/JSON-LD-Export mit SKOS | vorgeschlagen | Speicherformat und Veröffentlichungsformat sind trennbar |
| Gewichtungsmodell Attribution bei Graph-Antworten | offen | Steht einem Herausgeber etwas zu, wenn ohne Volltext geantwortet wurde? Als eigene Kategorie erfasst, vertraglich zu klären |
| Nutzungsvorbehalte je Quelle (§ 44b Abs. 3 UrhG) | laufende Aufgabe | Prüfung datiert und belegt im Quellenregister, mit Wiedervorlage |
| Rechtliche Bewertung je Rechtsraum | laufende Aufgabe | Braucht mittelfristig eine zuständige Rolle, keine einmalige Klärung |
| Apple-Provision bei digitalen Abos | offen | In der EU inzwischen Alternativen über externe Zahlungswege — vor Store-Release prüfen |
| Aufbewahrungsfristen der Sicherungskopien | offen | (Nutzerdaten: Höchstfristen in ADR-027 festgehalten.) Bestimmt, wie lange ein vernichteter Schlüssel vorgehalten werden muss, bevor Backups auslaufen |
| STACKIT-Repository `jwokittel/normly-webapp` | entschieden (2026-10-09): löschen | Der Betreiber löscht es im STACKIT-Portal (Nachtrag zu ADR-021); danach den Eintrag streichen |
| Personennamen im öffentlichen Wissensbestand-Dump | entschieden (2026-10-09): Rolle `normly maintainers` | Umgesetzt im Export (ADR-025); Eintrag nach dem ersten öffentlichen Dump streichen |
| Aufbewahrung und Alterung von Tombstones | offen | Ob Kennungen zurückgezogener Dokumente zeitlich begrenzt werden; ADR-027 hat es nicht entschieden (ADR-026) |
| Identität bei Neulieferung nach Widerruf | offen | Neue Dokumentknoten übernehmen Beobachtungen der Tombstones nicht; Produkt- und Identitätsentscheidung (ADR-026) |
| Signaturschlüssel des Wissensbestand-Dumps | offen | Schlüsselzeremonie, öffentlichen Schlüssel ins Repository einchecken (ADR-025) |
| Fachliche Prüfung der Aufbewahrungsfristen für Nutzerdaten | offen | Durch eine Fachperson für Datenschutz; dazu Datenschutzerklärung und Verzeichnis der Verarbeitungstätigkeiten als eigene Rechtstexte (ADR-027) |
| Löschen inaktiver Konten mit Vorwarnung | offen | Nicht umgesetzt; Frist und Warn-E-Mail entscheiden (ADR-027) |
| Sicherungen bei lizenzierten Beständen | offen | Kryptographisches Löschen (ADR-014) für die kommerzielle Schicht; Flex-PITR klären; Objektsperre vorerst bewusst nicht (ADR-024) |

**Hinweis:** Die rechtlichen Einschätzungen in diesem Dokument sind
Arbeitsgrundlage, keine Rechtsberatung. Insbesondere die Konstruktion
Trägerorganisation/GmbH, die Lizenzvertragsgestaltung und die
Urheberrechtsbewertung je Rechtsraum gehören vor eine fachkundige Prüfung.
