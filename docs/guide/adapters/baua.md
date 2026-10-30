# BAuA adapter status

> **Status reviewed:** 2026-10-29 (documentation/code review; no tests run for this status page)  
> **Implementation:** [`baua.py`](../../../core/src/normly_core/pipeline/adapters/baua.py)  
> **Design:** [BAuA adapter design](../../superpowers/specs/2026-09-01-baua-adapter-design.md)

This is a status snapshot of the BAuA adapter, not a legal opinion or a claim
that every BAuA-related system requirement is met. The adapter covers the TRGS,
TRBS, and TRBA series registered as a Category A source. It is currently an
operator-staged local-file ingestion path.

## Requirement mapping

| Requirement | Applicability to this adapter | Status relative to requirement | Evidence, gap, and disposition |
|---|---|---|---|
| [REQ-INT-002](../../srs/03-requirements.md#req-int-002-interface-to-norm-databases) | Adjacent, but its contractual Category C publisher-database integration is not BAuA's current Category A source scope. | **Not implemented by this adapter.** | BAuA files are manually staged locally; this adapter has no API/SFTP transport. Its PDF support does not satisfy REQ-INT-002. Assess system-level fulfillment separately; this status note does not establish that requirement as met elsewhere. |
| [REQ-PIPE-002](../../srs/03-requirements.md#req-pipe-002-source-register) | Applicable | **Partial.** | `baua` has a source-register entry with publisher, retrieval path, Category A, jurisdiction, and review date in [`sources.py`](../../../core/src/normly_core/pipeline/sources.py), but its responsible-person field is a placeholder. The adapter note does not establish that register changes are historized. Keep the requirement open until the responsible role and required history evidence are confirmed. |
| [REQ-PIPE-009](../../srs/03-requirements.md#req-pipe-009-initial-collection-from-freely-accessible-sources) | Applicable | **Partial contribution; overall acceptance not established here.** | The CLI builds the BAuA adapter and the shared pipeline consumes its records. This enables ingesting BAuA inputs but does not demonstrate a complete initial collection, automated acquisition, or system-level acceptance. |

REQ-INT-002 calls for automatic import of PDF/XML documents from a publisher's
database on a contractual Category C basis, via API or SFTP, with German and
English titles, version, publication date, and validity metadata. The BAuA
adapter is not that integration. Do not mark the system-level requirement
complete based on this adapter.

## Capability status

| Capability | State and scope | Evidence | Remaining work / disposition |
|---|---|---|---|
| Acquisition | **Complete for manual local-directory staging.** | `BauaAdapter` scans the directory supplied to it; `python -m normly_core.pipeline ingest baua --directory ...` is wired through the CLI. | No API/SFTP acquisition is implemented here. Such integration is outside the current Category A adapter scope; contractual partner ingestion must be assessed separately against REQ-INT-002. |
| PDF input | **Complete for the supported BAuA filename patterns.** | `baua_trgs_*.pdf`, `baua_trbs_*.pdf`, and `baua_trba_*.pdf`; extraction uses the shared Docling layer. | Layout and extraction limits are recorded below. This is not evidence of support for every possible PDF layout. |
| XML input | **Not implemented.** | The adapter discovers only `*.pdf`; no XML parser or XML tests exist. | No XML implementation is committed for the current BAuA scope. If XML becomes an agreed input for this adapter, define its mapping and tests first. |
| Designation and issuer | **Implemented with fail-closed identity handling.** | Searches bounded front matter for a unique TRGS/TRBS/TRBA designation. Filename hints only narrow candidates when corroborated in extracted text. Synthetic and local real-document checks cover selected cases. | Ambiguous or absent candidates remain unresolved for the existing review path. The behavior depends on Docling's extracted ordering and front-matter representation. |
| Title and metadata | **Partial.** | A short, clearly bounded title may be extracted; language is set to German; content hash and fetch time are recorded. | No English title, structured publication date, validity, or version extraction is implemented. `RawRecord.edition` is not populated by this adapter; `Teil N` remains part of the designation string rather than a structured part field. No metadata expansion is committed for this adapter. |
| Numbered section extraction | **Implemented conservatively; layout-dependent.** | Standalone numbered headings with accepted Docling labels are split in document order. Preamble is retained, ambiguous numbered prose stays in body, and a no-heading document falls back to one full-text section. | Merged headings or unsupported Docling classifications may be missed. See layout canaries and the locked-version verification gap below. |
| Shared pipeline persistence and embeddings | **Unverified for a BAuA end-to-end run.** | The shared runner stores extracted sections and embeddings when the rights rule permits indexing. | No BAuA-specific synthetic test currently runs extraction through database persistence and embedding creation. Add a CI-safe integration test with generated synthetic PDF input and a deterministic test embedder. |
| Semantic retrieval | **Unverified for BAuA content and the real embedding model.** | Repository-level similarity search is tested separately with controlled vectors in [`test_segment_similarity_search.py`](../../../core/tests/graph/test_segment_similarity_search.py). | Those tests do not prove BAuA end-to-end retrieval or real-model semantic quality. Keep a real-model check separate and local/offline unless a compliant pre-provisioned model test is established. |

The adapter's rights classification and source-register entry encode the
project's current Category A treatment. They are not a substitute for keeping
the source's legal classification and evidence valid under the repository's
source-register rules.

## Test coverage

| Behavior / risk | Coverage state | Test path or procedure | Input provenance | What is asserted | Gap / next action |
|---|---|---|---|---|---|
| Series discovery, designation/title parsing, ambiguity, filename corroboration, and extraction failures | **CI synthetic** | [`test_baua_adapter.py`](../../../core/tests/pipeline/test_baua_adapter.py) | PDFs generated at test time with ReportLab | TRGS/TRBS/TRBA patterns, optional `Teil N`, missing/competing identities, title fallback, unreadable-file isolation, and pipeline initialization failure behavior | Synthetic documents exercise designed layouts, not the distribution of real BAuA layouts. |
| Numbered section parsing and fallbacks | **CI synthetic** | [`test_baua_adapter.py`](../../../core/tests/pipeline/test_baua_adapter.py) | Generated synthetic PDFs and controlled adapter records | Heading splits, preamble retention, ambiguous numbered prose, conservative Docling labels, full-text fallback, and empty input | Does not by itself demonstrate real-source extraction accuracy. |
| Real PDF designation and section canaries | **Local real-source; opt-in** | [`test_baua_adapter_real.py`](../../../core/tests/pipeline/test_baua_adapter_real.py); instructions in repository `core/review.md` | Local `TRGS-401.pdf`, `TRGS-402.pdf`, and `TRGS-001.pdf`, kept outside Git | Designation and first/last headings for TRGS-401/402; unresolved identity for TRGS-001; contiguous section sequence | Not run by CI; only selected samples and boundaries are checked. The recorded real-document run used Docling 2.132.0; verification with locked 2.135.0 remains open. |
| pgvector ranking, rights gate, and model-name filtering | **CI integration, generic repository behavior** | [`test_segment_similarity_search.py`](../../../core/tests/graph/test_segment_similarity_search.py) | Controlled test vectors in disposable PostgreSQL | Similarity order, threshold, rights filtering, and model filter | Does not ingest BAuA records, call the real embedder, or establish semantic quality. |
| BAuA extraction through database segments, embeddings, and retrieval | **Not covered** | No BAuA-specific end-to-end test currently exists | — | — | Add synthetic CI integration coverage with a deterministic test embedder; keep real-model quality evaluation distinct. |
| XML input | **Not covered; unsupported** | No XML adapter tests | — | — | Implement and add format-specific tests only if XML is brought into the adapter's agreed scope. |

### Required local validation for BAuA-related changes

For every change to the BAuA adapter, its extraction/section behavior, or a
shared domain interface used by it, run the opt-in checks against all three
original local samples before treating the change as verified:
`TRGS-401.pdf`, `TRGS-402.pdf`, and `TRGS-001.pdf`. Run them from the repository
root, setting `BAUA_REAL_DOCUMENTS_DIR` to the directory containing those PDFs:

```bash
HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 \
BAUA_REAL_DOCUMENTS_DIR=/tmp/opencode/baua-review \
PYTHONPATH=core/src \
.venv/bin/pytest core/tests/pipeline/test_baua_adapter_real.py -vv
```

Require all three cases to **pass with zero skips**. The test intentionally
skips a case when its local file is missing, so a successful pytest exit with
skipped samples is not sufficient validation. If the originals are unavailable
or the check cannot run, report validation as outstanding; synthetic tests are
not a substitute.

The checks assert designations and first/last section headings for TRGS-401 and
TRGS-402, and that TRGS-001 remains unresolved. They test extraction only, not
database ingestion, embeddings, or retrieval. They stage temporary symlinks and
do not copy PDFs into the repository or print extracted text. Keep original
PDFs and extracted full text out of Git and CI, and process these files only
under the applicable source legal classification.

## Input-layout assumptions and drift checks

| Assumption / variant | Regression signal | Detection method and trigger | Response if it changes |
|---|---|---|---|
| Designation appears in bounded front matter and is unique; filename is only a corroborating hint. | A local sample resolves to an empty/wrong designation or becomes ambiguous. | Synthetic identity tests run in CI; the opt-in original-PDF canaries run locally for every BAuA adapter or related domain-interface change. | Inspect the changed extraction and source; update parser/tests only after confirming the new behavior. Keep uncertain identity fail-closed. |
| Section headings are short, standalone numbered Docling items with supported labels. | First/last real-sample heading assertions fail, or section sequence/headings differ after a source or Docling change. | Synthetic heading tests run in CI. Selected original PDFs are local canaries; rerun on BAuA changes and Docling upgrades. | Determine whether the source layout, Docling classification, or parser assumption changed. Add/update a regression case based on verified behavior; do not merely rewrite expected headings. |
| PDF layout remains within the variants represented by the local samples. | A new BAuA layout or edition behaves differently from the existing sample set. | **No automatic upstream layout monitoring.** Detection depends on a maintainer obtaining/being authorized to test a new representative local sample and running the real-document checks. | Record the new layout variant and its coverage. Extend local assertions or synthetic tests as appropriate without committing real PDFs or extracted full text. |

The synthetic fixtures are manually designed to exercise parser cases; they
are not publisher-layout monitors. The real-PDF checks are opt-in and test
extraction only. They stage temporary symlinks, do not write to a database,
and do not print extracted document text. If local samples are unavailable,
record the real-source validation as outstanding rather than treating
synthetic coverage as a substitute.

## Open work and non-goals

| Item | State | Next action / trigger | Owner or dependency |
|---|---|---|---|
| Validate real-PDF behavior with locked Docling 2.135.0 | **Open** | Run the opt-in canaries in the locked environment and record the result before relying on larger ingestion. | Local approved sample files and pinned project environment. |
| BAuA extraction-to-database/embedding/retrieval integration coverage | **Open** | Add a synthetic CI test using generated PDFs and deterministic embeddings; verify stored sections/embeddings and retrieved result. | Core pipeline tests; disposable pgvector test database. |
| XML support | **Not implemented; no current BAuA plan** | Revisit only if XML is an agreed source format for this adapter; then specify metadata and parsing behavior and add tests. | Scope decision and XML source/schema. |
| API/SFTP contractual publisher integration | **Out of scope for this Category A adapter** | Assess separately against REQ-INT-002 and Category C source-registration/contract requirements; do not count this adapter as fulfillment. | System-level integration design and contract basis. |
| Automatic detection of upstream BAuA layout changes | **Not implemented** | No automatic source monitoring is part of the current adapter. Reassess if a lawful, maintainable change-notification mechanism is available. | Upstream BAuA publication/access mechanism. |
| Structured bilingual/version/date/validity metadata | **Not implemented** | Revisit if those fields are required for this source and are available from a suitable structured source. | Domain/API scope and source metadata. |
