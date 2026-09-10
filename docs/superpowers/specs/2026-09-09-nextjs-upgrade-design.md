# Next.js/React/Vitest Major-Version Upgrade — Design

## Kontext

`frontend/`s `npm audit` meldet 6 Schwachstellen (2 kritisch, 2 hoch, 2
mittel), alle mit Fix nur über einen Major-Version-Sprung erreichbar:

- **Next.js** (kritisch, 23 gebündelte Advisories: DoS über den Image
  Optimizer, RSC-Deserialisierungs-DoS, Request-Smuggling bei Rewrites,
  Cache-Poisoning, XSS über CSP-Nonces, SSRF über WebSocket-Upgrades/
  Rewrites, unauthentifizierte RCE auf Windows-Servern und bei
  AVIF-Bildoptimierung). Fix: `next@16.3.4`.
- **postcss** (hoch, XSS über unescaped `</style>`, beliebiges Datei-Lesen
  über `sourceMappingURL`). Wird transitiv über `next/node_modules/postcss`
  reingezogen — fixt sich mit dem Next-Bump automatisch.
- **esbuild/vite/vitest** (mittel, Dev-Server-Response-Leak, nur
  Dev-Server-relevant, nicht im gebauten/deployten Code). Fix:
  `vite@8.2.2`.

Dieser Umbau war bewusst aus einem vorherigen Wartungs-Backlog
(`docs/superpowers/plans/2026-09-09-maintenance-backlog.md`, PR #21)
ausgeklammert, da er echte Breaking Changes mit sich bringt und eine
eigene Testrunde braucht.

**Vor dem Design falsch angenommene, jetzt korrigierte Fakten** (aus
direkter Code-Prüfung, nicht aus einer älteren Memory-Notiz übernommen):
Es gibt entgegen einer früheren Annahme doch eine eigene `middleware.ts`
(setzt ein anonymes ID-Cookie vor jedem Request, kein Redirect, keine
i18n-Logik — die Middleware/Proxy-Advisories betreffen sie nur am Rande).
Bestätigt weiterhin korrekt: kein `next/image`, keine Server Actions, kein
Pages-Router-Code (`getServerSideProps`/`getStaticProps` kommen nirgends
vor). Es existiert noch kein Dockerfile/Compose-Setup im Repo — das
CLAUDE.md-Deployment-Artefakt ist ein späteres, separates Vorhaben und hier
nicht betroffen. Die PWA-Funktionalität ist handgerollt (statische
`public/service-worker.js` + eine kleine Registrierungs-Komponente, kein
`next-pwa`/Workbox) und von diesem Umbau völlig unberührt.

## Zielversionen

| Paket | Aktuell | Ziel | Grund |
|---|---|---|---|
| `next` | `^14.2.0` | `16.3.4` | schließt die kritische Advisory-Gruppe |
| `react` / `react-dom` | `^18.3.0` | `^19.x` (neueste) | vom Nutzer gewählter voller Umbau; `next@16` akzeptiert beides, `next@14` NUR `^18.2.0` — bestimmt die Reihenfolge unten |
| `@types/react` / `@types/react-dom` | `^18.3.0` | `^19.x` | passend zu React 19 |
| `@testing-library/react` | `^15.0.0` | `^16.3.3` | erste Version mit offizieller React-19-Unterstützung (`react: ^18.0.0 \|\| ^19.0.0`) |
| `vitest` | `^1.6.0` | `^5.0.0` | vom Nutzer gewählter voller Umbau statt nur der Minimalversion `3.2.6` |
| `vite` | `^5.4.0` | `^8.2.2` | von `vitest@5` verlangt (`vite: ^6.4.0 \|\| ^7.0.0 \|\| ^8.0.0`) und deckt selbst die esbuild-Advisory |
| `@vitejs/plugin-react` | `^4.3.0` | `^6.1.1` | verlangt `vite ^8.0.0` |
| `@types/node` | `^20.14.0` | `^22.0.0` | `vitest@5` verlangt `^22.0.0 \|\| >=24.0.0` — `^20.x` wird nicht mehr unterstützt |
| `postcss` (eigene Devdependency) | `^8.4.0` | unverändert (löst durch frischen Install/Lockfile-Update automatisch auf ≥8.5.23) | die gemeldete Schwachstelle betrifft die von `next` intern gebündelte Kopie, nicht direkt diese Zeile |

**Kaskadeneffekt, vom Nutzer explizit bestätigt**: `vitest@5`s
`@types/node`-Anforderung zwingt zu einer echten Node-Runtime-Anhebung.
Die CI (`.forgejo/workflows/ci.yml`, Job `test-frontend`) läuft aktuell im
Container `node:20` — wird auf `node:22` (aktuelle LTS-Linie) umgestellt.
`next@16` selbst bräuchte nur `>=20.9.0`, aber die vitest-Kaskade bestimmt
hier die tatsächliche Untergrenze.

## Architektur

Ein Plan, 5 gestufte Tasks in dieser Reihenfolge — jede Task ist einzeln
testbar und einzeln revertierbar (eigener Commit), sodass ein Fehler auf
genau ein Paket/eine Stufe eingrenzbar bleibt:

1. **Test-Tooling** (`vitest`, `vite`, `@vitejs/plugin-react`,
   `@types/node`) + CI-Node-Bump. Next.js und React bleiben unverändert.
   Gate: `npm test` (die komplette Vitest-Suite) grün.
2. **Next.js 16** (`next`). React bleibt bewusst auf 18.3, da `next@16`
   das explizit unterstützt — vermeidet einen Peer-Dependency-Konflikt mit
   dem noch nicht angehobenen React (siehe Zielversionen-Tabelle).
   `next.config.mjs` kann optional zu `.ts` werden (die bestehende Datei
   trägt schon einen Kommentar, der genau auf diese jetzt aufgehobene
   14.x-Beschränkung verweist). Gate: `next build` läuft durch, Vitest-Suite
   weiterhin grün, `tsc --noEmit` clean.
3. **React 19** (`react`, `react-dom`, `@types/react`,
   `@types/react-dom`, `@testing-library/react`). Erst jetzt sicher, weil
   `next@16` beide React-Linien akzeptiert. Gate: Vitest-Suite grün,
   `tsc --noEmit` clean.
4. **Produktions-Build + volle E2E-Suite als Staging-Ersatz-Gate**: die
   echten Backend-Services (`accounts`/`api`/`chat` + Postgres) starten,
   `npm run build && npm run start` (genau das, was
   `playwright.config.ts`s `webServer.command` bereits automatisch tut),
   dann die komplette bestehende Playwright-Suite
   (`search-and-browse.spec.ts`, `chat-and-history.spec.ts`,
   `account-management.spec.ts`, `accessibility.spec.ts`) gegen echte Daten
   laufen lassen. Da es kein separates Staging gibt, ist das der
   eigentliche Beweis, dass der neue Stack im echten Produktions-Build
   funktioniert, nicht nur unter `next dev`/Vitest-Mocks.
5. **Audit-Abschlusskontrolle**: frischer `npm audit`-Lauf muss 0 Findings
   zeigen; `package-lock.json` final committen.

## Fehlerbehandlung / Rollback

Kein Merge nach `main`, solange Task 4 nicht grün ist — das ersetzt das
fehlende Staging als Sicherheitsnetz. Jede Task landet als eigener Commit;
ein `git revert` einer einzelnen Task-Commit-Range ist möglich, ohne die
anderen Stufen anzufassen, falls nach dem Merge doch noch ein Problem
auffällt.

## Testing

- Task 1-3: jeweils die volle bestehende Vitest-Unit-Suite (aktuell 206
  Tests über 56 Dateien) plus `tsc --noEmit`.
- Task 4: volle Playwright-E2E-Suite gegen einen echten Produktions-Build
  und echte, laufende Backend-Services — kein Mocking.
- Task 5: `npm audit` als reiner Verifikationsschritt, kein Code-Fix mehr
  nötig, wenn Tasks 1-3 korrekt durchgeführt wurden.

## Globale Leitplanken

- Kein Wechsel des App-Router-Modells, keine Einführung von Server
  Actions/`next/image`/neuer Middleware-Logik — nur die Versions-Bumps
  selbst, keine neuen Next-Features.
- `output: "standalone"` bleibt unverändert (ADR-010).
- Die bestehende `middleware.ts` (Anonym-ID-Cookie) bleibt inhaltlich
  unverändert — nur mitgetestet, nicht umgebaut.
- `frontend/README.md`s BFF-Konventionen (Session-Cookie-Handling,
  Google-OAuth-Redirect-Pfad, siehe auch
  `docs/superpowers/plans/2026-09-09-maintenance-backlog.md`s eigene
  OAuth-Lektion) bleiben unangetastet.
- Lizenzheader (nur bei neuen Dateien — dieser Umbau erstellt
  voraussichtlich keine), DCO `Signed-off-by` (`git commit -s`),
  Conventional Commits, separater `Co-Authored-By: Claude Sonnet 5
  <noreply@anthropic.com>`-Trailer auf jedem Commit.
- Kein Push/PR/Merge ohne explizite Rückfrage vorher (STACKIT-CI-Läufe
  sind kostenpflichtig, kein funktionierendes Cancel).
