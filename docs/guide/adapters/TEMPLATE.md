# <Publisher> adapter status

> **Status reviewed:** YYYY-MM-DD  
> **Implementation:** [`<adapter>.py`](../../../core/src/normly_core/pipeline/adapters/)  
> **Status evidence:** State the code revision and dependency versions used for
> verification. A documentation review alone is not a test run.

## Scope

Describe the source, document series, acquisition boundary, and what this
adapter does not own. Link its design/specification and source-register entry.

## Status vocabulary

Use one of these states for every applicable capability and requirement:

- **Complete** — the stated scope and acceptance criteria are met; no known
  work remains in that scope.
- **Partial** — some criteria are met. Name the missing criteria and state
  whether follow-up is planned, open but unscheduled, or out of scope.
- **Not implemented** — the capability is absent. State whether it is planned,
  an open gap, or explicitly out of scope; do not imply that absence is a
  committed plan.
- **Unverified** — implementation appears to exist, but adequate test or
  operational evidence is missing. Name the verification needed.
- **Blocked** — progress depends on a named decision, permission, or external
  dependency, with an owner or resolution trigger where known.
- **Not applicable** — explain why, with a link to the relevant scope or
  requirement decision.

Words such as “manual”, “local”, “automatic”, and “PDF” describe a capability's
mode or scope; they are not status values. Every non-Complete entry must have a
clear disposition and next action (or explicitly say there is no planned work).

## Requirement mapping

| Requirement | Applicability to this adapter | Status relative to requirement | Evidence, gap, and disposition |
|---|---|---|---|
| REQ-... | Applicable / adjacent / not applicable (explain) | Complete / Partial / Not implemented / Unverified / Blocked / N/A | Link evidence and state the remaining work or why none is planned. |

Do not mark a system-level requirement complete based only on one adapter's
capability. Distinguish an adapter's scope from integration work that belongs
to a partner interface or another component.

## Capability status

| Capability | State and scope | Evidence | Remaining work / disposition |
|---|---|---|---|
| Acquisition and transport |  |  |  |
| Input formats |  |  |  |
| Identity and metadata |  |  |  |
| Content and structure extraction |  |  |  |
| Rights and processing gate |  |  |  |
| Downstream persistence / retrieval |  |  |  |
| Error handling / idempotence |  |  |  |

Include only relevant rows, but account for every row as applicable or
Not applicable with a reason. Name supported file extensions and acquisition
methods precisely.

## Test coverage

Record actual evidence, not just test files that happen to exist. Use a coverage
state of **CI synthetic**, **CI integration**, **local real-source**, **manual**,
or **Not covered**. Explain opt-in requirements and known limitations.

| Behavior / risk | Coverage state | Test path or procedure | Input provenance | What is asserted | Gap / next action |
|---|---|---|---|---|---|
| Discovery / supported formats |  |  |  |  |  |
| Identity and metadata |  |  |  |  |  |
| Structure and fallback behavior |  |  |  |  |  |
| Rights gate and failure cases |  |  |  |  |  |
| Persistence, lineage, and idempotence |  |  |  |  |  |
| Embedding / retrieval, if applicable |  |  |  |  |  |

For each check, say whether CI runs it or it must be run locally. Identify
external services, database containers, model artifacts, or local source files
it needs. Synthetic tests establish behavior for their generated inputs; do
not present them as proof of real-source layout compatibility or model quality.

## Input-layout assumptions and drift checks

| Assumption / variant | Regression signal | Detection method and frequency/trigger | Response if it changes |
|---|---|---|---|
|  |  |  |  |

State explicitly whether upstream layout changes are monitored automatically.
Describe which tests act as canaries, which source variants they cover, and
which changes (for example, a source redesign or parser-library upgrade) require
rerunning them. When updating an expected result, first verify the changed
source extraction and explain why the test expectation changed.

## Open work and non-goals

| Item | State | Next action / trigger | Owner or dependency |
|---|---|---|---|
|  | Open / Blocked / Not planned / Out of scope |  |  |

Do not put copyrighted source documents or extracted full text in the
repository. Explain how any local-only evidence can be run without committing
the source material.
