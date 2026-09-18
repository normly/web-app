# normly

**AI-assisted standards and technical rules, open to everyone.**

normly makes knowledge about standards and Regelwerke as freely accessible as
the law allows — and builds an open, machine-readable reference graph on top
of it: which Regelwerke reference each other, what was superseded by what,
and which legal provision references which standard.

> ⚠️ **Early development stage.** This repository is under construction.
> There is no working release yet and no stable API.

## Why

Anyone who wants to know which standard applies to a task, whether it's still
valid, and what it superseded, finds no good answer today. Regelwerke are
scattered across different publishers, their cross-references are nowhere
captured in a machine-readable way, and many freely available texts —
accident-prevention regulations, technical rules, EU directives — are public
in principle but hard to find in practice.

normly is built for the people who work with this material every day:
skilled trades, planning, occupational safety, and small to medium
businesses.

## What's free and what isn't

normly follows an **open-core model**. The line runs through content, not
through the access path.

**Free** — the core, the reference graph, and all content that may be freely
redistributed: official works, DGUV Regeln, BAuA technical rules, EU
directives via EUR-Lex, open standards. Usable without an account, without
payment, self-hostable.

**Paid** — managed hosting with an SLA, compliance instances with an audit
trail, integrations into CAD and ERP systems, and instances with
contractually licensed full texts of standards.

Copyrighted full texts are **not** redistributed freely. Where they are
processed, that happens on a contractual basis — with revenue share for the
publishers.

What normly explicitly does **not** do: no personalized advertising, no user
profiles for advertising purposes, no scraping of commercially exploited
standards catalogs.

## Licenses

| Component | License |
|---|---|
| Core (server, application) | AGPL-3.0 |
| Client SDKs, API specification | Apache-2.0 |
| Data and reference graph | ODbL |
| `normly` trademark | see [TRADEMARK.md](TRADEMARK.md) |

The AGPL applies when someone modifies and operates the server itself. A
third-party system that talks to a normly instance over the HTTP API is a
separate program and unaffected — integrations are explicitly welcome.

## Contributing

Contributions go through the **Developer Certificate of Origin** (DCO), not
a transfer of rights. Every commit needs a `Signed-off-by` line:

```bash
git commit -s -m "feat: short description"
```

Details in [CONTRIBUTING.md](CONTRIBUTING.md). Please **do not** report
security vulnerabilities as an issue — see [SECURITY.md](SECURITY.md).

## Running Locally

To run the complete stack locally using Docker Compose:

```bash
docker compose up --build
```

- Web UI: [http://localhost:3000](http://localhost:3000)
- Graph API Docs: [http://localhost:8002/docs](http://localhost:8002/docs)
- Accounts API Docs: [http://localhost:8001/docs](http://localhost:8001/docs)

To seed sample data:
```bash
./scripts/seed-data.sh --compose
```

For native development with hot-reloading (`./scripts/dev-setup.sh` and `./scripts/dev-run.sh`) or direct database querying, see the [Local Development Guide](docs/guide/local-development.md).

## Where the code lives

Source code, contributions, CI/CD, and the container registry for the free
core live on **GitHub**: [github.com/normly/web-app](https://github.com/normly/web-app)
(ADR-021) — easier collaboration was the reason for the move back. Operations,
user data, and the future standards knowledge base stay separate from that
and remain exclusively on STACKIT infrastructure in Germany.

## Documentation

| | |
|---|---|
| [docs/srs/](docs/srs/) | Requirements (SRS/SDD), 78 requirements |
| [docs/adr/](docs/adr/) | Architecture decisions with rationale |
| [docs/normly_Verarbeitungskette.svg](docs/normly_Verarbeitungskette.svg) | From source to delivery |
| [docs/normly_Entwicklungsphasen.svg](docs/normly_Entwicklungsphasen.svg) | Phase plan |
| [CLAUDE.md](CLAUDE.md) | Working instructions for AI-assisted development |

If you want to understand **why** something is the way it is: `docs/adr/`
is the right place to start.

## Status

First working prototype: December 2026. The reference graph is built from
freely accessible sources — it needs no licensing agreement.

---

<sub>normly is an independent project and has no affiliation with DIN, VDI,
ISO, CEN, or other standards organizations.</sub>
