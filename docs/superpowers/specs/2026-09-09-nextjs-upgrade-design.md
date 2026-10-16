# Next.js/React/Vitest Major-Version Upgrade — Design

## Context

`frontend/`'s `npm audit` reports 6 vulnerabilities (2 critical, 2 high, 2
moderate), all of them fixable only via a major version jump:

- **Next.js** (critical, 23 bundled advisories: DoS via the Image
  Optimizer, RSC deserialization DoS, request smuggling with rewrites,
  cache poisoning, XSS via CSP nonces, SSRF via WebSocket upgrades/
  rewrites, unauthenticated RCE on Windows servers and with
  AVIF image optimization). Fix: `next@16.3.4`.
- **postcss** (high, XSS via unescaped `</style>`, arbitrary file read
  via `sourceMappingURL`). Pulled in transitively via `next/node_modules/postcss`
  — fixes itself automatically with the Next bump.
- **esbuild/vite/vitest** (moderate, dev server response leak, relevant only to the
  dev server, not in the built/deployed code). Fix:
  `vite@8.2.2`.

This rework was deliberately excluded from a previous maintenance backlog
(`docs/superpowers/plans/2026-09-09-maintenance-backlog.md`, PR #21),
because it brings real breaking changes and needs a
test round of its own.

**Facts wrongly assumed before the design, now corrected** (from
direct code inspection, not taken over from an older memory note):
Contrary to an earlier assumption, there is in fact a `middleware.ts` of our own
(sets an anonymous ID cookie before every request, no redirect, no
i18n logic — the middleware/proxy advisories affect it only marginally).
Still confirmed as correct: no `next/image`, no Server Actions, no
Pages Router code (`getServerSideProps`/`getStaticProps` occur nowhere).
No Dockerfile/Compose setup exists in the repo yet — the
CLAUDE.md deployment artifact is a later, separate undertaking and is
not affected here. The PWA functionality is hand-rolled (a static
`public/service-worker.js` + a small registration component, no
`next-pwa`/Workbox) and completely untouched by this rework.

## Target versions

| Package | Current | Target | Reason |
|---|---|---|---|
| `next` | `^14.2.0` | `16.3.4` | closes the critical advisory group |
| `react` / `react-dom` | `^18.3.0` | `^19.x` (latest) | full rework chosen by the owner; `next@16` accepts both, `next@14` ONLY `^18.2.0` — determines the order below |
| `@types/react` / `@types/react-dom` | `^18.3.0` | `^19.x` | matching React 19 |
| `@testing-library/react` | `^15.0.0` | `^16.3.3` | first version with official React 19 support (`react: ^18.0.0 \|\| ^19.0.0`) |
| `vitest` | `^1.6.0` | `^5.0.0` | full rework chosen by the owner instead of only the minimum version `3.2.6` |
| `vite` | `^5.4.0` | `^8.2.2` | required by `vitest@5` (`vite: ^6.4.0 \|\| ^7.0.0 \|\| ^8.0.0`) and itself covers the esbuild advisory |
| `@vitejs/plugin-react` | `^4.3.0` | `^6.1.1` | requires `vite ^8.0.0` |
| `@types/node` | `^20.14.0` | `^22.0.0` | `vitest@5` requires `^22.0.0 \|\| >=24.0.0` — `^20.x` is no longer supported |
| `postcss` (own devDependency) | `^8.4.0` | unchanged (resolves automatically to ≥8.5.23 through a fresh install/lockfile update) | the reported vulnerability concerns the copy bundled internally by `next`, not this line directly |

**Cascade effect, explicitly confirmed by the owner**: `vitest@5`'s
`@types/node` requirement forces a real Node runtime upgrade.
The CI (`.forgejo/workflows/ci.yml`, job `test-frontend`) currently runs in the
container `node:20` — it is switched to `node:22` (the current LTS line).
`next@16` itself would only need `>=20.9.0`, but the vitest cascade determines
the actual lower bound here.

## Architecture

One plan, 5 staged tasks in this order — each task is individually
testable and individually revertible (its own commit), so that a failure
can be narrowed down to exactly one package/one stage:

1. **Test tooling** (`vitest`, `vite`, `@vitejs/plugin-react`,
   `@types/node`) + CI Node bump. Next.js and React stay unchanged.
   Gate: `npm test` (the complete Vitest suite) green.
2. **Next.js 16** (`next`). React deliberately stays on 18.3, since `next@16`
   explicitly supports that — avoids a peer dependency conflict with
   the not yet upgraded React (see the target versions table).
   `next.config.mjs` can optionally become `.ts` (the existing file
   already carries a comment that points to exactly this now lifted
   14.x restriction). Gate: `next build` completes, Vitest suite
   still green, `tsc --noEmit` clean.
3. **React 19** (`react`, `react-dom`, `@types/react`,
   `@types/react-dom`, `@testing-library/react`). Only safe now, because
   `next@16` accepts both React lines. Gate: Vitest suite green,
   `tsc --noEmit` clean.
4. **Production build + full E2E suite as a substitute gate for staging**: start the
   real backend services (`accounts`/`api`/`chat` + Postgres),
   `npm run build && npm run start` (exactly what
   `playwright.config.ts`'s `webServer.command` already does automatically),
   then run the complete existing Playwright suite
   (`search-and-browse.spec.ts`, `chat-and-history.spec.ts`,
   `account-management.spec.ts`, `accessibility.spec.ts`) against real data.
   Since there is no separate staging, this is the
   actual proof that the new stack works in the real production build,
   not just under `next dev`/Vitest mocks.
5. **Final audit check**: a fresh `npm audit` run must show 0 findings;
   commit the final `package-lock.json`.

## Error handling / rollback

No merge to `main` as long as Task 4 is not green — this replaces the
missing staging as a safety net. Each task lands as its own commit;
a `git revert` of a single task's commit range is possible without touching the
other stages, should a problem still turn up after the
merge.

## Testing

- Tasks 1-3: the full existing Vitest unit suite each time (currently 206
  tests across 56 files) plus `tsc --noEmit`.
- Task 4: full Playwright E2E suite against a real production build
  and real, running backend services — no mocking.
- Task 5: `npm audit` as a pure verification step, no code fix needed
  any more if Tasks 1-3 were carried out correctly.

## Global guardrails

- No change of the App Router model, no introduction of Server
  Actions/`next/image`/new middleware logic — only the version bumps
  themselves, no new Next features.
- `output: "standalone"` stays unchanged (ADR-010).
- The existing `middleware.ts` (anonymous ID cookie) stays unchanged in
  content — only tested along with the rest, not rebuilt.
- `frontend/README.md`'s BFF conventions (session cookie handling,
  Google OAuth redirect path, see also
  `docs/superpowers/plans/2026-09-09-maintenance-backlog.md`'s own
  OAuth lesson) stay untouched.
- License headers (only for new files — this rework
  is not expected to create any), DCO `Signed-off-by` (`git commit -s`),
  Conventional Commits, a separate `Co-Authored-By: Claude Sonnet 5
  <noreply@anthropic.com>` trailer on every commit.
- No push/PR/merge without asking explicitly first (STACKIT CI runs
  are billed, no working cancel).
