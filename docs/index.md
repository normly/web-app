# normly

**AI-assisted standards and regulations, open to everyone.**

normly makes knowledge about standards and regulations as freely
accessible as legally possible — and builds on that an open,
machine-readable reference graph: which regulations reference each
other, what replaced what, and which legal requirement points to which
standard.

!!! warning "Early development stage"
    This project is under construction. There is no runnable version yet
    and no stable API — this documentation site grows with the code.
    First runnable prototype: December 2026.

## Where to go next

- **[Guide](guide/getting-started.md)** — getting started for users and
  operators
- **[Concepts](concepts/normen-graph.md)** — the underlying principles
  (graph first, license model)
- **[Architecture decisions](adr/README.md)** — why it's built the way
  it's built
- **[Requirements](srs/README.md)** — the 78 requirements (SRS/SDD)
- **[Code reference](reference/core.md)** — generated automatically from
  docstrings, for contributors

Architecture decisions and Requirements are currently German-only; the
rest of the site is in English, and full translation is tracked
separately.

## Licenses

| Component | License |
|---|---|
| Core (server, application) | AGPL-3.0 |
| Client SDKs, API specification | Apache-2.0 |
| Data and reference graph | ODbL |

Details and rationale are in `README.md` and `GOVERNANCE.md` at the
repository root.
