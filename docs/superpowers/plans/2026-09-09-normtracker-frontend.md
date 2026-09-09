# Frontend (Normtracker Teil 5/5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the three visually-underdesigned areas of the app (Document-Detail, Search, Watchlist/Notification UI) a real design pass, adapting three concrete `@shadcnblocks` reference blocks (`resource3`, `list1`, `settings-notifications2`) onto our existing, unchanged data and BFF routes.

**Architecture:** Pure frontend remapping, no backend changes anywhere. Each of the four tasks below touches one existing component (plus its test file and any i18n keys it needs) and installs the one or two shadcn/ui base components it specifically needs. Every existing `data-testid` and every existing BFF route call stays exactly as it is today — only the surrounding markup, layout, and (in Task 4 only) the interaction model changes.

**Tech Stack:** Next.js (App Router) + React + TypeScript, Tailwind, shadcn/ui + `@shadcnblocks` registry, Vitest + Testing Library.

## Global Constraints

- No new backend endpoints, no `core/` or `accounts/` changes whatsoever — every component keeps calling exactly the BFF routes it calls today (`/api/documents/*`, `/api/documents/search`, `/api/account/watchlist`, `/api/account/notifications`, `/api/account/profile`), with the exact same request/response shapes.
- No new filters, sorting, or search functionality — the search filter form (`Input`×2 + `Button`) and the `Pagination` component stay structurally exactly as they are.
- Do not touch `app-shell.tsx`, the `PageHeader`'s outer `Popover`/`PopoverTrigger`/`PopoverContent` wrapper structure (only its `PopoverContent` children), chat pages, or auth pages.
- Every existing `data-testid` must be preserved exactly, unchanged, in its exact current form: `validity-badge`, `edition-history-list`, `national-adoptions-list`, `references-list`, `watchlist-toggle` (in `document-detail-content.tsx`), `notification-{id}` (in `page-header.tsx`).
- No visual-regression/E2E tooling introduced — Vitest unit tests only, extending each file's existing conventions exactly.
- Every existing test's BEHAVIORAL assertion (does the heart toggle actually add/remove, does search actually return and paginate results, does markRead actually PATCH, does the notification-preference section actually PATCH the right value) must keep passing. Only selectors/markup-shape assertions may change to match new structure — never loosen or delete a behavioral assertion.
- New i18n keys go into BOTH `frontend/src/lib/i18n/de.json` and `en.json`, in the same section and the same relative position in both files — `tests/unit/i18n.test.tsx` fails the whole suite if the two dictionaries' key sets ever diverge. Remove keys from both files together too, never from just one.
- License headers (`// SPDX-License-Identifier: AGPL-3.0-or-later` / `// Copyright (C) 2026 normly contributors`) on every new file.
- DCO (`Signed-off-by`, via `git commit -s`) + Conventional Commits on every commit; add `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` as a separate trailer, never as the DCO signoff.
- TDD throughout: for each task, first make the test fail against the CURRENT markup (or write a wholly new test that fails because the new element doesn't exist yet), confirm the failure reason, then implement, then confirm it passes.
- `frontend/components.json` already has `@shadcnblocks` configured (`url: https://www.shadcnblocks.com/r/{name}`, `Authorization: Bearer ${SHADCNBLOCKS_API_KEY}` header) — block-fetch commands below are copy-pasteable as-is. Already-installed shadcn/ui base components (confirmed this session, do NOT reinstall): `avatar`, `badge`, `button`, `collapsible`, `dialog`, `dropdown-menu`, `input`, `pagination`, `popover`, `scroll-area`, `separator`, `sheet`, `sidebar`, `skeleton`, `tabs`, `textarea`, `tooltip`. Missing and needed by this plan: `table` (Task 2), `switch` (Task 4). `breadcrumb` is also missing and needed by Task 1.

---

### Task 1: Document-Detail two-column layout (resource3-based)

**Files:**
- Modify: `frontend/src/app/documents/[id]/document-detail-content.tsx`
- Modify: `frontend/tests/unit/document-detail-page.test.tsx`
- Modify: `frontend/src/lib/i18n/de.json`
- Modify: `frontend/src/lib/i18n/en.json`

**Interfaces:**
- Consumes: nothing new — `DocumentDetail`, `WorkStructure`, `RightsClassification`, `ValiditySummary`, `ResolvedEdge` interfaces, the two existing `useEffect`s, `toggleWatch`, and every piece of state (`isWatched`, `isTogglingWatch`, `watchError`) are UNCHANGED. This task only rewrites the function's `return (...)` JSX.
- Produces: no new exports. The five `data-testid`s (`validity-badge`, `edition-history-list`, `national-adoptions-list`, `references-list`, `watchlist-toggle`) stay on exactly the same elements they're on today (a `Badge`, two `<ul>`s, one more `<ul>`, one `<button>`) — only their surrounding container markup changes.

- [ ] **Step 1: Install the missing shadcn/ui base component**

Run: `cd frontend && npx shadcn@latest add breadcrumb`
Expected: creates `frontend/src/components/ui/breadcrumb.tsx`. (`separator` is already installed — confirm with `ls src/components/ui/separator.tsx` before assuming you need to add it too.)

- [ ] **Step 2: Write the failing test for the heart's new position**

Add this test to `frontend/tests/unit/document-detail-page.test.tsx`, right after the existing `"shows an empty heart for a logged-in visitor..."` test:

```typescript
  it("places the watchlist toggle next to the title, not in the rights sidebar", async () => {
    mockFetch({
      account: {
        accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
        avatarDataUrl: null, hasPassword: true, notificationPreference: "none",
      },
      watchlist: [],
    });

    renderDetail(DOCUMENT_ID);

    const heading = await screen.findByRole("heading", { name: "EN ISO 9001:2018" });
    const toggle = await screen.findByTestId("watchlist-toggle");
    // The heart must be a sibling of (or nested alongside) the title heading,
    // inside the same header block -- not inside the sidebar that holds the
    // rights checklist and the source link.
    expect(heading.parentElement).toContainElement(toggle);
  });
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/document-detail-page.test.tsx -t "places the watchlist toggle"`
Expected: FAIL — the heart is currently rendered in its own `<div>` well below the title, not as a sibling inside the title's own parent element.

- [ ] **Step 4: Add the breadcrumb i18n key**

In `frontend/src/lib/i18n/de.json`, inside the existing `"nav"` section (has `chat`, `search`, `account`, etc. — add right after `"account"`):
```json
"breadcrumbHome": "Start",
```
In `frontend/src/lib/i18n/en.json`, same section, same position:
```json
"breadcrumbHome": "Home",
```

- [ ] **Step 5: Rewrite the component's JSX**

Replace the entire `return (...)` block in `document-detail-content.tsx` (everything from `return (` to the final closing `);` before the function's closing `}`) with:

```tsx
  return (
    <div>
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link href="/search">{t("nav.breadcrumbHome")}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{primaryDesignation}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="mt-4 flex items-center gap-3">
        <h2 className="text-xl font-semibold">{primaryDesignation}</h2>
        {account && workStructure && (
          <div className="flex flex-col gap-1">
            <button
              type="button"
              onClick={toggleWatch}
              disabled={isTogglingWatch}
              aria-label={t(isWatched ? "documentDetail.removeFromWatchlist" : "documentDetail.addToWatchlist")}
              data-testid="watchlist-toggle"
            >
              <Heart className={isWatched ? "h-5 w-5 fill-current" : "h-5 w-5"} />
            </button>
          </div>
        )}
      </div>
      {watchError && (
        <p className="mt-1 text-sm text-destructive">{t("documentDetail.watchlistToggleError")}</p>
      )}
      {primaryTitle && <p className="mt-1 text-muted-foreground">{primaryTitle}</p>}

      {validity && (
        <Badge
          className="mt-3"
          variant={validity.status === "valid" ? "default" : "outline"}
          data-testid="validity-badge"
        >
          {t(VALIDITY_KEYS[validity.status])}
        </Badge>
      )}

      <div className="relative mt-8 grid gap-10 md:grid-cols-3">
        <div className="flex flex-col gap-6 md:col-span-2">
          {workStructure && workStructure.editions.length > 0 && (
            <div>
              <h3 className="font-medium">{t("documentDetail.editionsHeading")}</h3>
              <ul className="mt-2 flex flex-col gap-2" data-testid="edition-history-list">
                {workStructure.editions.map((entry) => (
                  <li
                    key={entry.document_id}
                    className="flex items-center gap-2 rounded-md border p-2"
                  >
                    <Badge variant={entry.status === "valid" ? "default" : "outline"}>
                      {t(VALIDITY_KEYS[entry.status])}
                    </Badge>
                    <Link href={`/documents/${entry.document_id}`} className="underline">
                      {entryLabel(entry)}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {workStructure && workStructure.national_adoptions.length > 0 && (
            <div>
              <h3 className="font-medium">{t("documentDetail.adoptionsHeading")}</h3>
              <ul className="mt-2 flex flex-col gap-2" data-testid="national-adoptions-list">
                {workStructure.national_adoptions.map((entry) => (
                  <li
                    key={entry.document_id}
                    className="flex items-center gap-2 rounded-md border p-2"
                  >
                    <Badge variant={entry.status === "valid" ? "default" : "outline"}>
                      {t(VALIDITY_KEYS[entry.status])}
                    </Badge>
                    <Link href={`/documents/${entry.document_id}`} className="underline">
                      {entryLabel(entry)}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {edges.length > 0 && (
            <div>
              <h3 className="font-medium">{t("documentDetail.referencesHeading")}</h3>
              <ul className="mt-2 flex flex-col gap-2" data-testid="references-list">
                {edges.map((edge) => (
                  <li
                    key={`${edge.edge_type}-${edge.to_document_id}`}
                    className="flex items-center gap-2 rounded-md border p-2"
                  >
                    <Badge variant="muted">{t(EDGE_TYPE_KEYS[edge.edge_type] ?? "edgeType.references")}</Badge>
                    <Link href={`/documents/${edge.to_document_id}`} className="underline">
                      {edge.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="h-fit md:sticky md:top-20">
          {rights && (
            <div className="rounded-lg border p-4">
              <h3 className="mb-3 text-sm font-medium">{t("documentDetail.rightsHeading")}</h3>
              <ul className="flex flex-col gap-2 text-sm">
                <li className="flex items-center gap-2">
                  {rights.may_process ? (
                    <CircleCheck className="h-4 w-4 text-primary" />
                  ) : (
                    <CircleX className="h-4 w-4 text-muted-foreground" />
                  )}
                  {t("documentDetail.mayProcess")}
                </li>
                <li className="flex items-center gap-2">
                  {rights.may_index_fulltext ? (
                    <CircleCheck className="h-4 w-4 text-primary" />
                  ) : (
                    <CircleX className="h-4 w-4 text-muted-foreground" />
                  )}
                  {t("documentDetail.mayIndexFulltext")}
                </li>
                <li className="flex items-center gap-2">
                  {rights.may_cite_passages ? (
                    <CircleCheck className="h-4 w-4 text-primary" />
                  ) : (
                    <CircleX className="h-4 w-4 text-muted-foreground" />
                  )}
                  {t("documentDetail.mayCitePassages")}
                </li>
                <li className="flex items-center gap-2">
                  {rights.may_export_free ? (
                    <CircleCheck className="h-4 w-4 text-primary" />
                  ) : (
                    <CircleX className="h-4 w-4 text-muted-foreground" />
                  )}
                  {t("documentDetail.mayExportFree")}
                </li>
              </ul>
              <p className="mt-3 text-xs text-muted-foreground">{rights.legal_basis_reference}</p>
              <Separator className="my-4" />
              <Button asChild size="sm" className="w-full">
                <a href={documentDetail.source.retrieval_path} target="_blank" rel="noopener noreferrer">
                  {documentDetail.source.publisher}
                </a>
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
```

Add the new imports at the top of the file (right after the existing `import { Heart } from "lucide-react";`):

```tsx
import { CircleCheck, CircleX } from "lucide-react";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
```

Note two things this rewrite deliberately does:
1. **The "Quelle öffnen" action now uses `documentDetail.source.publisher` as its visible label** (matching the old link's own text) wrapped in a `Button` — the link target (`documentDetail.source.retrieval_path`) is unchanged. This is not a new field, just a new visual treatment of the exact same two existing fields.
2. **The rights checklist card and the source-button are only rendered when `rights` is truthy** (same condition the current code already uses) — when `rights` is `null` (not yet loaded, or the document has no classification), the sidebar column renders empty, which is fine — no placeholder needed for a case the current code already treats as "nothing to show."

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run tests/unit/document-detail-page.test.tsx`
Expected: PASS — all 10 tests (9 existing + the 1 new one from Step 2).

- [ ] **Step 7: Run the full frontend suite**

Run: `cd frontend && npx vitest run`
Expected: PASS (192+ tests — 191 baseline + the 1 new test).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/documents/\[id\]/document-detail-content.tsx \
  frontend/tests/unit/document-detail-page.test.tsx \
  frontend/src/lib/i18n/de.json frontend/src/lib/i18n/en.json \
  frontend/src/components/ui/breadcrumb.tsx frontend/package.json frontend/package-lock.json
git commit -s -m "feat(frontend): restructure the document detail page into a two-column resource3 layout"
```

(Add `frontend/package.json`/`package-lock.json` only if `npx shadcn add breadcrumb` actually changed them — check `git status` first; the breadcrumb component itself has no extra npm dependency beyond what's already installed, so they may be unchanged.)

---

### Task 2: Search results table (list1-based)

**Files:**
- Modify: `frontend/src/app/search/search-page-content.tsx`
- Modify: `frontend/tests/unit/search-page.test.tsx`

**Interfaces:**
- Consumes: nothing new — `WorkSearchResult`, `SearchResponse`, `runSearch`, `submit` are UNCHANGED. This task only rewrites the results-rendering JSX (the `<ul>` block) into a `<Table>`.
- Produces: no new exports, no new `data-testid`s needed (existing tests query by `role`/`text`, which this task preserves).

- [ ] **Step 1: Install the missing shadcn/ui base component**

Run: `cd frontend && npx shadcn@latest add table`
Expected: creates `frontend/src/components/ui/table.tsx`.

- [ ] **Step 2: Write the failing test for the new table structure**

Add this test to `frontend/tests/unit/search-page.test.tsx`, right after the existing `"submits the query and renders a result as a link..."` test:

```typescript
  it("renders results as a table with issuer and designation columns", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          results: [
            {
              work_id: "22222222-2222-2222-2222-222222222222",
              best_match: {
                id: "11111111-1111-1111-1111-111111111111",
                origin_issuer: "DGUV", origin_number: "Vorschrift 1",
                designations: [{ designation: "DGUV Vorschrift 1", is_primary: true }],
              },
              other_editions_count: 0,
            },
          ],
          total: 1,
        }),
        { status: 200 },
      ),
    );

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Suchen" }));

    await waitFor(() => expect(screen.getByRole("table")).toBeInTheDocument());
    expect(screen.getByRole("columnheader", { name: "Herausgeber" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Bezeichnung" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "DGUV" })).toBeInTheDocument();
  });
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/search-page.test.tsx -t "renders results as a table"`
Expected: FAIL — `screen.getByRole("table")` finds nothing, since results currently render as a `<ul>`.

- [ ] **Step 4: Add the two new i18n keys**

In `frontend/src/lib/i18n/de.json`, inside the existing `"search"` section, right after `"otherEditions"`:
```json
"issuerColumnHeading": "Herausgeber",
"designationColumnHeading": "Bezeichnung",
```
In `frontend/src/lib/i18n/en.json`, same section, same position:
```json
"issuerColumnHeading": "Issuer",
"designationColumnHeading": "Description",
```

- [ ] **Step 5: Rewrite the results block**

In `search-page-content.tsx`, replace the entire block from `{response !== null && response.results.length > 0 && (` through its matching `)}` with:

```tsx
      {response !== null && response.results.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("search.issuerColumnHeading")}</TableHead>
                <TableHead>{t("search.designationColumnHeading")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {response.results.map(({ work_id, best_match, other_editions_count }) => {
                const primary =
                  best_match.designations.find((d) => d.is_primary) ?? best_match.designations[0];
                return (
                  <TableRow key={work_id}>
                    <TableCell>{best_match.origin_issuer}</TableCell>
                    <TableCell>
                      <Link href={`/documents/${best_match.id}`} className="underline">
                        {primary?.designation ?? `${best_match.origin_issuer} ${best_match.origin_number}`}
                      </Link>
                      {other_editions_count > 0 && (
                        <span className="ml-2 text-sm text-muted-foreground">
                          +{other_editions_count} {t("search.otherEditions")}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          <Pagination
            offset={offset}
            limit={PAGE_SIZE}
            total={response.total}
            onPageChange={runSearch}
            previousLabel={t("search.previousPage")}
            nextLabel={t("search.nextPage")}
          />
        </>
      )}
```

Add the import at the top of the file (right after the existing `Pagination` import):

```tsx
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run tests/unit/search-page.test.tsx`
Expected: PASS — all 5 tests (4 existing + the 1 new one). The existing `"shows an other-editions count..."` and `"submits the query and renders a result as a link..."` tests need NO changes to their own assertions — they query by `role="link"` and by literal text, both of which still exist unchanged inside the new `TableCell`.

- [ ] **Step 7: Run the full frontend suite**

Run: `cd frontend && npx vitest run`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/search/search-page-content.tsx \
  frontend/tests/unit/search-page.test.tsx \
  frontend/src/lib/i18n/de.json frontend/src/lib/i18n/en.json \
  frontend/src/components/ui/table.tsx
git commit -s -m "feat(frontend): render search results as a table instead of a plain list"
```

---

### Task 3: Bell popover activity-feed styling

**Files:**
- Modify: `frontend/src/components/page-header.tsx`

**Interfaces:**
- Consumes: nothing new — `useNotifications()`'s `notifications`/`markRead` and the existing `TRIGGER_TYPE_KEYS` map are UNCHANGED. This task only rewrites the `PopoverContent`'s non-empty branch (the `<ul>` of buttons).
- Produces: no new exports, no test-file changes needed at all — every existing assertion in `page-header.test.tsx` (translated title, no subtitle, sidebar toggle, empty-list message, 401/anonymous, and `notification-n1` + `markRead`) targets either text that doesn't change (`"Keine neuen Benachrichtigungen"`) or the `data-testid="notification-{id}"` anchor, which stays on the same clickable element.

- [ ] **Step 1: Write the new failing test**

Add this test to `frontend/tests/unit/page-header.test.tsx`, right after the existing `"lists real notifications and marks one read on click"` test:

```typescript
  it("shows an icon and a formatted date on each notification row", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "n1", workId: "w1", triggerType: "new_edition", triggerDocumentId: null,
            triggerJurisdiction: null, createdAt: "2026-01-15T00:00:00Z", readAt: null,
          },
        ]),
        { status: 200 },
      ),
    );

    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Benachrichtigungen" }));
    const item = await screen.findByTestId("notification-n1");

    expect(within(item).getByText("Ersetzt")).toBeInTheDocument();
    expect(within(item).getByText(new Date("2026-01-15T00:00:00Z").toLocaleDateString("de"))).toBeInTheDocument();
  });
```

Add `within` to the existing `import { render, screen, fireEvent, waitFor } from "@testing-library/react";` line at the top of the file (`import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";`).

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/page-header.test.tsx -t "shows an icon and a formatted date"`
Expected: FAIL — the current row renders only the translated trigger-type label and an unread badge, no date.

- [ ] **Step 3: Rewrite the popover's non-empty branch**

In `page-header.tsx`, replace the entire `<ul className="flex flex-col gap-2">...</ul>` block (the `else` branch of the `notifications.length === 0 ? ... : ...` ternary) with:

```tsx
              <ul className="flex flex-col gap-1">
                {notifications.map((notification) => (
                  <li key={notification.id}>
                    <button
                      type="button"
                      data-testid={`notification-${notification.id}`}
                      onClick={() => markRead(notification.id)}
                      className="flex w-full items-start gap-2 rounded-md p-2 text-left text-sm hover:bg-muted"
                    >
                      {notification.readAt === null ? (
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                      ) : (
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0" />
                      )}
                      <TriggerTypeIcon
                        triggerType={notification.triggerType}
                        className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                      />
                      <span className="flex flex-col">
                        <span>{t(TRIGGER_TYPE_KEYS[notification.triggerType] ?? "nav.notificationsLabel")}</span>
                        <span className="text-xs text-muted-foreground">
                          {new Date(notification.createdAt).toLocaleDateString(locale)}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
```

Add a small icon-mapping helper right above the `PageHeader` function (after the existing `TRIGGER_TYPE_KEYS` constant):

```tsx
import { Bell, FileDiff, Globe, Scale } from "lucide-react";

const TRIGGER_TYPE_ICONS: Record<string, typeof FileDiff> = {
  new_edition: FileDiff,
  national_adoption: Globe,
  rights_change: Scale,
};

function TriggerTypeIcon({ triggerType, className }: { triggerType: string; className?: string }) {
  const Icon = TRIGGER_TYPE_ICONS[triggerType] ?? Bell;
  return <Icon className={className} />;
}
```

(Replace the existing `import { Bell } from "lucide-react";` line with the combined import above — `Bell` is still used both as the fallback icon here and as the popover trigger's own icon further down in the file, unchanged.)

Add `locale` to the existing `const { t } = useTranslation();` line, changing it to `const { t, locale } = useTranslation();`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run tests/unit/page-header.test.tsx`
Expected: PASS — all 8 tests (7 existing + the 1 new one). None of the 7 existing tests' own assertions need to change.

- [ ] **Step 5: Run the full frontend suite**

Run: `cd frontend && npx vitest run`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/page-header.tsx frontend/tests/unit/page-header.test.tsx
git commit -s -m "feat(frontend): show an icon and date on each bell popover notification"
```

---

### Task 4: Notification-preference switches (settings-notifications2-based)

**Files:**
- Modify: `frontend/src/components/account/notification-preference-section.tsx`
- Modify: `frontend/tests/unit/notification-preference-section.test.tsx`
- Modify: `frontend/src/lib/i18n/de.json`
- Modify: `frontend/src/lib/i18n/en.json`

**Interfaces:**
- Consumes: nothing new — `AccountSummary`/`onAccountUpdated` props and the `PATCH /api/account/profile` call with `{notification_preference: <value>}` are UNCHANGED in shape; only HOW the four possible string values (`"none"`/`"in_app"`/`"email"`/`"both"`) get computed changes (from a direct radio-value read to a derived combination of two independent booleans).
- Produces: no new exports. This is the one task in this plan with a genuinely different interaction model (2 independent switches instead of 4 mutually-exclusive radio options), not just a visual restyle — its test file is REWRITTEN, not extended.

- [ ] **Step 1: Install the missing shadcn/ui base component**

Run: `cd frontend && npx shadcn@latest add switch`
Expected: creates `frontend/src/components/ui/switch.tsx`.

- [ ] **Step 2: Replace the i18n keys**

In `frontend/src/lib/i18n/de.json`, inside the `"account"` section, REMOVE these four now-unused keys: `notificationPreferenceNone`, `notificationPreferenceInApp`, `notificationPreferenceEmail`, `notificationPreferenceBoth`. Keep `notificationPreferenceTitle` and `notificationPreferenceSaveError` exactly as they are. Add these four new keys in their place (same position in the `"account"` section):
```json
"notificationChannelInAppTitle": "In der Software",
"notificationChannelInAppDescription": "Zeigt Änderungen im Glocken-Symbol an.",
"notificationChannelEmailTitle": "Per E-Mail",
"notificationChannelEmailDescription": "Sendet dir eine E-Mail bei Änderungen.",
```

In `frontend/src/lib/i18n/en.json`, same section, same four keys removed, same four keys added in the same position:
```json
"notificationChannelInAppTitle": "In the app",
"notificationChannelInAppDescription": "Shows changes in the bell icon.",
"notificationChannelEmailTitle": "By email",
"notificationChannelEmailDescription": "Sends you an email when something changes.",
```

- [ ] **Step 3: Write the new, replacing test file**

Replace the ENTIRE content of `frontend/tests/unit/notification-preference-section.test.tsx` with:

```typescript
// frontend/tests/unit/notification-preference-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { NotificationPreferenceSection } from "@/components/account/notification-preference-section";
import type { AccountSummary } from "@/lib/account-response";

const originalFetch = global.fetch;

function makeAccount(notificationPreference: string): AccountSummary {
  return {
    accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
    avatarDataUrl: null, hasPassword: true, notificationPreference,
  };
}

describe("NotificationPreferenceSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows both switches off when the preference is none", () => {
    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("none")} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    expect(screen.getByLabelText("In der Software")).not.toBeChecked();
    expect(screen.getByLabelText("Per E-Mail")).not.toBeChecked();
  });

  it("shows only the in-app switch on when the preference is in_app", () => {
    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("in_app")} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    expect(screen.getByLabelText("In der Software")).toBeChecked();
    expect(screen.getByLabelText("Per E-Mail")).not.toBeChecked();
  });

  it("shows only the email switch on when the preference is email", () => {
    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("email")} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    expect(screen.getByLabelText("In der Software")).not.toBeChecked();
    expect(screen.getByLabelText("Per E-Mail")).toBeChecked();
  });

  it("shows both switches on when the preference is both", () => {
    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("both")} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    expect(screen.getByLabelText("In der Software")).toBeChecked();
    expect(screen.getByLabelText("Per E-Mail")).toBeChecked();
  });

  it("turning the email switch on from in_app computes both", async () => {
    const onAccountUpdated = vi.fn();
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(makeAccount("both")), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("in_app")} onAccountUpdated={onAccountUpdated} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByLabelText("Per E-Mail"));

    await waitFor(() => expect(onAccountUpdated).toHaveBeenCalled());
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ notification_preference: "both" });
  });

  it("turning the in-app switch off from both computes email", async () => {
    const onAccountUpdated = vi.fn();
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(makeAccount("email")), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("both")} onAccountUpdated={onAccountUpdated} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByLabelText("In der Software"));

    await waitFor(() => expect(onAccountUpdated).toHaveBeenCalled());
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ notification_preference: "email" });
  });

  it("disables both switches while a save is in flight", async () => {
    let resolveFetch: ((response: Response) => void) | undefined;
    global.fetch = vi.fn().mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("none")} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByLabelText("In der Software"));

    await waitFor(() => expect(screen.getByLabelText("In der Software")).toBeDisabled());
    expect(screen.getByLabelText("Per E-Mail")).toBeDisabled();

    resolveFetch!(new Response(JSON.stringify(makeAccount("in_app")), { status: 200 }));

    await waitFor(() => expect(screen.getByLabelText("In der Software")).not.toBeDisabled());
  });

  it("reverts to the account's own state and shows an error when saving fails", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "something went wrong" }), { status: 500 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("none")} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByLabelText("In der Software"));

    await waitFor(() =>
      expect(
        screen.getByText("Einstellung konnte nicht gespeichert werden. Bitte versuche es erneut."),
      ).toBeInTheDocument(),
    );
    // account.notificationPreference is still "none" (the prop never changed,
    // since onAccountUpdated is only called on a successful response) -- the
    // switch must reflect that, not stay optimistically "on".
    expect(screen.getByLabelText("In der Software")).not.toBeChecked();
  });
});
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run tests/unit/notification-preference-section.test.tsx`
Expected: FAIL — `screen.getByLabelText("In der Software")` finds nothing, since the component still renders four radio inputs labeled `"Keine Benachrichtigungen"`/`"Nur in der Software"`/`"Nur per E-Mail"`/`"Software und E-Mail"`, not two switches.

- [ ] **Step 5: Rewrite the component**

Replace the ENTIRE content of `frontend/src/components/account/notification-preference-section.tsx` with:

```tsx
// frontend/src/components/account/notification-preference-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Switch } from "@/components/ui/switch";
import { useTranslation } from "@/lib/i18n/provider";
import type { AccountSummary } from "@/lib/account-response";

function computePreference(isInApp: boolean, isEmail: boolean): string {
  if (isInApp && isEmail) return "both";
  if (isInApp) return "in_app";
  if (isEmail) return "email";
  return "none";
}

export function NotificationPreferenceSection({
  account, onAccountUpdated,
}: {
  account: AccountSummary;
  onAccountUpdated: (account: AccountSummary) => void;
}) {
  const { t } = useTranslation();
  const [status, setStatus] = React.useState<"idle" | "error">("idle");
  const [isSaving, setIsSaving] = React.useState(false);

  const isInApp = account.notificationPreference === "in_app" || account.notificationPreference === "both";
  const isEmail = account.notificationPreference === "email" || account.notificationPreference === "both";

  const save = async (nextIsInApp: boolean, nextIsEmail: boolean) => {
    setIsSaving(true);
    try {
      const response = await fetch("/api/account/profile", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ notification_preference: computePreference(nextIsInApp, nextIsEmail) }),
      });
      if (response.ok) {
        setStatus("idle");
        onAccountUpdated(await response.json());
      } else {
        setStatus("error");
      }
    } catch {
      setStatus("error");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">{t("account.notificationPreferenceTitle")}</h2>
      <div className="divide-y">
        <div className="flex items-center justify-between gap-4 py-3">
          <div className="space-y-0.5">
            <p className="text-sm font-medium">{t("account.notificationChannelInAppTitle")}</p>
            <p className="text-sm text-muted-foreground">{t("account.notificationChannelInAppDescription")}</p>
          </div>
          <Switch
            aria-label={t("account.notificationChannelInAppTitle")}
            checked={isInApp}
            disabled={isSaving}
            onCheckedChange={(checked) => save(checked, isEmail)}
          />
        </div>
        <div className="flex items-center justify-between gap-4 py-3">
          <div className="space-y-0.5">
            <p className="text-sm font-medium">{t("account.notificationChannelEmailTitle")}</p>
            <p className="text-sm text-muted-foreground">{t("account.notificationChannelEmailDescription")}</p>
          </div>
          <Switch
            aria-label={t("account.notificationChannelEmailTitle")}
            checked={isEmail}
            disabled={isSaving}
            onCheckedChange={(checked) => save(isInApp, checked)}
          />
        </div>
      </div>
      {status === "error" && (
        <p className="text-sm text-destructive">{t("account.notificationPreferenceSaveError")}</p>
      )}
    </section>
  );
}
```

(`aria-label` on each `Switch` is what makes `screen.getByLabelText("In der Software")` resolve to it in the tests above — the shadcn `Switch` is a plain button-role element, not wrapped in a `<label>`, so this is the correct accessible-name mechanism for it, unlike the old radio inputs which used a wrapping `<label>`.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run tests/unit/notification-preference-section.test.tsx`
Expected: PASS — all 8 tests.

- [ ] **Step 7: Run the full frontend suite**

Run: `cd frontend && npx vitest run`
Expected: PASS — check in particular that `tests/unit/i18n.test.tsx`'s de/en key-parity test still passes (it will, since Step 2 added and removed the same four keys in both files).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/account/notification-preference-section.tsx \
  frontend/tests/unit/notification-preference-section.test.tsx \
  frontend/src/lib/i18n/de.json frontend/src/lib/i18n/en.json \
  frontend/src/components/ui/switch.tsx
git commit -s -m "feat(frontend): rebuild the notification-preference section as two independent switches"
```
