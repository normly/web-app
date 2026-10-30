# Adapter status

These notes describe what each source adapter currently supports, how that
status is verified, and what remains open. They are implementation snapshots,
not substitutes for requirements or design decisions. Requirement status is
assessed per adapter; one adapter's limitation does not by itself determine
whether the whole system meets a requirement.

Use the [adapter status template](TEMPLATE.md) when adding a note. Keep the
status note current with adapter changes as required by the local Core review
guide at `core/review.md` in the repository root.

## Adapters

| Adapter | Source / scope | Status note | Implementation |
|---|---|---|---|
| BAuA | TRGS, TRBS, TRBA | [BAuA adapter status](baua.md) | [`baua.py`](../../../core/src/normly_core/pipeline/adapters/baua.py) |

Other adapters will be added as their status is documented.
