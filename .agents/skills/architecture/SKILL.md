---
name: architecture
description: Use when tracing a feature across normly components, deciding where code belongs, or changing a component boundary or shared interface.
---

# Architecture skill

Start with the contributor-facing [architecture overview](../../../docs/guide/architecture.md).
Use this skill when a task crosses package boundaries or could change data
ownership, persistence, service interfaces, or the request flow.

## Trace a change

1. Locate the behavior in the component map in the architecture overview.
2. Read the related ADR and SRS requirement before changing a boundary or
   externally visible behavior.
3. Follow the call path through the owning package, its repository or client
   interface, and the corresponding tests.
4. Keep persistence details behind `core` repositories; keep cross-service
   communication behind HTTP clients and schemas.
5. Update tests and relevant requirements or decision records when the
   behavior or architecture changes.

Apply the component responsibilities in the architecture overview and the
repository-wide constraints in [`AGENTS.md`](../../../AGENTS.md); do not
restate those boundaries here. For a new cross-component decision, use the
specifications skill to decide whether an ADR or SRS update is needed.
