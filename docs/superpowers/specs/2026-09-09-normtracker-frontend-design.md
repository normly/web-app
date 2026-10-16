# Design: Frontend (Normtracker foundation, part 5/5)

## Context

All four backend sub-projects of the Normtracker foundation are done and
merged: work entity (PR #11), semantic search (PR #12), document detail
(PR #13) and watchlist/notification (PR #18), plus two inserted
prerequisite sub-projects (edition change detection PR #14,
edition-aware identity resolution PR #15). The entire backend surface
that this last sub-project has to present already exists: work-grouped
hybrid search (`search_works_for_jurisdiction`), a
document detail page with edition history/national versions/references/
rights, and the watchlist/notification surface (favorite heart, bell,
profile setting) — the latter already wired up with real data, but
deliberately built without a design of its own ("no new design, just real data",
as sub-project 4 itself laid down).

This sub-project is the last of the 5-part roadmap and takes over the
role of the originally paused Plan 6 ("Search & document detail",
re-theme only) from the separate 6-plan shadcn redesign — with a larger scope,
since three further backend sub-projects have since created real content
that Plan 6 did not yet know about. Plans 1-5 of this redesign (theme foundation,
app shell, chat page, profile overlay structure, auth pages) are already
done and provide the basis (shadcn default theme, light/dark, app shell
with sidebar, `PageHeader` pattern, profile overlay as a dialog). For
search/document detail/watchlist UI, **deliberately no
reference block** was fixed back then — that is the central decision
to be made anew here.

## Goal of this sub-project

Three areas that are functionally done so far but visually underdesigned
get a real design pass, all in the same sub-project:

1. **Document detail page** — a two-column layout instead of single-column
   bare flex sections.
2. **Search** — the result list as a real table instead of a bare `<ul>`.
3. **Watchlist/notification UI** — the bell popover content and the
   profile notification section get real, styled building blocks instead of
   raw components.

All three areas build exclusively on already existing
backend endpoints and data shapes — pure frontend remapping.

## Non-goals

- **No new backend endpoints or data model changes.** Every
  component keeps binding exactly the same BFF routes/response shapes
  that already exist.
- **No new filters, sort options or search functions.** The filter bar
  (free text + publisher) and pagination stay structurally unchanged.
- **No new notification trigger logic.** `notify-watchers` and the
  rights/edition detection stay unchanged; only the presentation of the
  already created notifications changes.
- **No changes to the app shell, the `PageHeader` frame (only its
  bell popover *content*), the chat page or the auth pages.** These are already
  done from Plans 1-5 and are not touched here.
- **No visual regression test (Playwright screenshots).** There is
  so far no E2E test infrastructure in this roadmap; the existing
  Vitest unit tests are extended, no new test tooling is introduced.
- **No separate jurisdiction/language switcher rework.**
  `JurisdictionSwitcher`/`LocaleSwitcher` stay unchanged.

## Architecture

### Document detail page

Reference block: **`resource3`** (two-column resource page with
breadcrumb and a fixed sidebar), with one explicit deviation: the
favorite heart sits **directly next to the title**, not in the sidebar
(where the original block has its social share row).

- **Header area**: breadcrumb (Home › current document), title row with
  the primary designation, favorite heart toggle directly next to it, below that the
  validity badge.
- **Main column** (left, most of the width): edition history and
  national versions as styled rows — each row: status badge
  (valid/replaced/withdrawn) + designation as a link, modeled on the
  `changelog8` row pattern (badge + text instead of a bare `<li>`). References
  below in the same row style, but with an edge type badge instead of a
  status badge (as today).
- **Sidebar** (right, fixed while scrolling — `md:sticky md:top-20`,
  modeled on `resource3`): rights checklist (✓/✗ per permission
  `may_process`/`may_index_fulltext`/`may_cite_passages`/`may_export_free`,
  modeled on `resource3`'s "Key Features" checklist with `CheckCircle2`), below that
  an "Open source" button that links to `documentDetail.source.retrieval_path`
  (replaces today's bare link).
- New registry dependencies: `breadcrumb`, `separator` (if not yet
  installed — check; `avatar`/`button` are already present).
- All existing `data-testid` anchors (`validity-badge`, `edition-history-
  list`, `national-adoptions-list`, `references-list`, `watchlist-toggle`)
  are kept, so that existing tests without a behavior change only have to adapt their
  markup surroundings, not their core assertion.

### Search

Reference block: **`list1`** ("Multi-column data table"), reduced to the
data that actually exists. The original has 6 columns (icon, category,
description, year, offer, segment) — our `WorkSearchHit` response has
only publisher, designation and `other_editions_count`. What is adopted is the
**table structure** (`Table`/`TableHeader`/`TableBody`/`TableRow`/
`TableCell` from shadcn/ui), not the number of columns:

- Column 1: publisher (`best_match.origin_issuer`).
- Column 2: designation (primary designation, link to the document detail page)
  plus a badge "+N editions" if `other_editions_count > 0`.
- **No icon column** — present in the original block, not relevant
  for us, deliberately left out (explicit owner decision).
- The filter bar (free-text input, publisher input, search button) and the
  `Pagination` component stay structurally exactly as today — only the
  result list itself becomes a table.
- Empty state: a card of its own with a subtle frame instead of a plain
  `<p>` paragraph.
- New registry dependency: `table` (shadcn/ui base component, not
  `@shadcnblocks`).

### Watchlist/notification UI

Two building blocks that already work but are underdesigned get a real
design — no new structure, no new logic:

**Bell popover** (`page-header.tsx`): the `Popover`/`PopoverTrigger`/
`PopoverContent` frame stays exactly as it is (Plans 1-5); only the content of
`PopoverContent` becomes real list rows in activity feed style
(modeled on `list-panel-list-activity-feed`, without avatar/`ItemMedia` — instead
a small icon per trigger type, analogous to the existing edge type icons
on the document detail page): icon + title (from the existing
`TRIGGER_TYPE_KEYS` mapping) + time (relative time from `createdAt`) +
a blue dot for unread (`readAt === null`). A click on a row still calls
`markRead`, exactly as today.

**Profile notification section** (`notification-preference-section.tsx`):
completely rebuilt on **`settings-notifications2`** ("Simple Switch List").
The block uses independent `Switch` toggles instead of a 4-way radio —
explicit owner decision, two independent channel switches instead of a
choice among four options:

- Switch "In the app" (`in_app` on/off)
- Switch "By email" (`email` on/off)
- **Both can be toggled fully independently of each other** (explicitly
  confirmed, no master switch relationship).
- Client-side state mapping onto the existing 4-value backend enum
  (`NotificationPreference`), unchanged:
  - both off → `none`
  - only "In the app" on → `in_app`
  - only "By email" on → `email`
  - both on → `both`
- Every switch click immediately triggers a `PATCH /api/account/profile`
  (same route, same error path checked via `response.ok` as today),
  with the `notification_preference` value computed from both switch states
  — no separate "Save" button.
- New registry dependency: `switch` (shadcn/ui base component).

**Favorite heart** (`document-detail-content.tsx`): no block
template of its own needed (a simple icon button), but a new placement directly
next to the title (see the document detail section above) instead of in the
rights sidebar.

## Data flow

No new backend endpoints. Affected, unchanged BFF routes:
`/api/documents/{id}`, `/api/documents/{id}/edges`, `/api/documents/{id}/
validity`, `/api/documents/{id}/work`, `/api/documents/{id}/rights`,
`/api/documents/search`, `/api/account/watchlist` (GET/POST/DELETE),
`/api/account/notifications` (GET/PATCH), `/api/account/profile` (PATCH).
New/changed shadcn/ui dependencies (`table`, `switch`, `breadcrumb`,
`separator`) are installed via the shadcn CLI; the referenced
`@shadcnblocks` blocks (`resource3`, `list1`, `settings-notifications2`)
are fetched via the same CLI and adapted to our real data/routes
(the blocks' demo data is replaced completely, as in Plans 1-5).

## Error handling

No new error handling needed — every component takes over exactly the
existing error path of its respective data source unchanged (e.g.
`toggleWatch`'s `response.ok` check with an error message, the search rate limit
display, the profile sections' error messages). The switch-based
notification section takes over the existing error behavior of the
`PATCH /api/account/profile` route 1:1 (error text on a non-`ok` response,
no optimistic toggling on failure — the same principle as in the
favorite heart fix from sub-project 4).

## Test concept

Existing Vitest suites are extended, not replaced:

- `document-detail-page.test.tsx`: existing assertions stay the same in
  content (edition history/versions/references/rights/watchlist toggle
  present and functional), only selectors/markup expectations are adapted to the new
  two-column layout. New assertion: the heart button sits in the
  title area, not in the sidebar.
- Search test(s): existing assertions on hits/pagination/empty state
  stay the same in content, selectors adapted to the new `Table` structure
  (`role="table"`/`role="row"` instead of `<ul>`/`<li>`).
- `page-header.test.tsx`: existing assertions (empty/anonymous/real list/
  `markRead`) stay the same in content, only the rendered row elements
  change according to the new activity feed markup.
- `notification-preference-section.test.tsx`: completely rewritten for
  the two-switch interaction — both switches can be toggled independently,
  each of the four combinations sends the correct `notification_preference`
  value, error state on a non-`ok` response.

No visual regression test (see Non-goals).
