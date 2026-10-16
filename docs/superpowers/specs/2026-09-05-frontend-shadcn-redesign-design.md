# Design: Frontend redesign on the shadcn default theme

## Context

The frontend is functionally complete (chat, search, document detail, account
management, auth modal), but visually unfinished: only seven raw
shadcn base components (`avatar`, `badge`, `button`, `dialog`, `input`,
`pagination`, `tabs`) in the Slate default style, no consistent
theming decision, no light/dark switch. A sandbox test run
in this session (screenshots) shows this clearly: working but
completely unstyled pages.

The project already has access to `@shadcnblocks` (premium registry,
`SHADCNBLOCKS_API_KEY` set, configured in `frontend/components.json`)
and to the shadcn MCP server for component discovery. The owner has
specified concrete reference blocks from this registry for every area of the app,
as well as an external reference layout (shadcnuikit.com's `ai-chat-v2`, only as
a visual template for the chat history, not a registered registry of its own).

## Goal of this sub-project

1. Switch to the shadcn default theme (light/dark) as the sole
   color system, no tenant branding color.
2. New app shell with a collapsible sidebar (`application-shell2`),
   main items Chat and Search.
3. The chat page gets a second, nested sidebar for the
   date-grouped history including a "New chat" button (modeled on
   shadcnuikit's `ai-chat-v2`), replacing the previous standalone
   `/chats` page.
4. Uniform page header pattern (modeled on `dashboard9`): title/
   subtitle on the left, dark/light toggle and notification bell
   (placeholder) on the right.
5. Profile management as a blurred overlay dialog (modeled on the
   `settings-profile4` structure, Claude-like presentation instead of a
   full page), with real account sections instead of the block's demo fields.
6. Five dedicated full-page auth pages (`/login`, `/signup`, `/magic-link`,
   `/reset-password`, `/verify-email`) after the blocks `signup2`,
   `magic-link2`, `reset-password2`, `verify-email2`, replacing the previous
   auth modal.
7. Search and document detail get no new layout, only the new
   theme colors/components, and from now on run inside the app shell.

## Non-goals

- **No tenant branding color.** `NORMLY_BRAND_COLOR_HSL` and the
  associated logic in `frontend/src/lib/config.ts` remain untouched in the
  code (a separate requirement, REQ-DIST-003), but are not wired into the new
  color tokens anywhere in this sub-project. Pure
  shadcn standard palette.
- **No new backend endpoints or auth flow changes.** In particular,
  email verification remains token-link based (see below,
  deviation for `verify-email2`).
- **No real notification feature.** The bell in the header is a pure
  UI element without a data source.
- **No new block layout for search/document detail.** Only
  color/component adaptation to the new theme.
- **None of the demo navigation items from the reference templates**
  (Dashboard, Tasks, Team, Workspace, Kanban, Mail, Hotel etc. from
  `application-shell2`/`dashboard9`/shadcnuikit) — they are trimmings of the
  templates, not part of this app.

## Architecture

### Theme foundation

- `@shadcnblocks/theme/shadcnblocks` provides the standard shadcn CSS
  variables (`--primary`, `--secondary`, `--accent`, `--muted`,
  `--destructive`, `--sidebar-*`, `--chart-1..5`, `--radius-*`,
  `--shadow-*`) for light and dark in `src/app/globals.css`.
- `next-themes` is newly introduced (`ThemeProvider` around the root layout)
  and provides the light/dark state for the toggle in the header.
- `tailwind.config.ts` is extended with the new color utilities
  (`primary`, `secondary`, `sidebar`, `chart-*` etc.); the existing
  `brand`/`brand-foreground` mappings remain, but are no longer
  referenced by any new component.

### App shell

- `application-shell2` provides the basic structure: a collapsible
  (icon-only capable) sidebar, content area (`SidebarInset`).
  Registry dependencies that must be newly installed: `sidebar`,
  `collapsible`, `dropdown-menu`, `scroll-area`, `separator` (avatar is
  already present).
- The demo's nav groups (Overview/Projects/Team/Workspace) are replaced
  by exactly two main items: **Chat**, **Search**.
- The user footer (`NavUser` pattern from the block) stays structurally the same:
  avatar + name/email, dropdown with "Account" (opens the
  profile overlay, see below) and "Sign out".
- From now on this shell wraps all pages (chat, search,
  document detail) — replacing the current simple top nav header.

### Chat page (nested sidebar)

- A second, inner sidebar **only on the chat page**: chat history grouped by
  creation date (buckets "Today", "Yesterday", "Previous 7 days",
  older analogously), "New chat" button at the top, modeled on ai-chat-v2 (only
  structure/layout, no third-party registry dependency — built as our own
  component, not imported).
- Data source: the existing `/api/chat/sessions` BFF route (already
  exists) — grouping happens client-side based on the
  session creation date.
- The previous standalone `/chats` history page is dropped; the
  top nav link "History" disappears, the history only lives in this
  inner sidebar, reachable via the Chat menu item of the outer sidebar.
- The chat window itself is rebuilt with shadcn components
  (message list, input field at the bottom instead of at the top as before) — existing
  citations ("Source" links under each answer) remain functionally
  unchanged, only visually new.

### Header pattern

- Shared layout component (`PageHeader` or similar): title + subtitle
  on the left (e.g. "Chat", "Search" — shows the current area), on the right a
  dark/light toggle button (`next-themes`) and a bell icon button
  (popover with static "No new notifications" content, no
  real data source).
- Used by every page below the app shell.

### Profile overlay

- Structure taken from `settings-profile4` (internal
  section navigation on the left, content on the right, "Save" bar), but:
  - **As a dialog/overlay**, not a full page: blurred background
    (`backdrop-blur`), the dialog does not take up the full width
    (Claude-like), similar to the previous auth modal, only larger.
  - **Sections adapted to real account data**, not to the
    block's demo fields (name/bio/social links/timezone are dropped). Real
    sections: profile (name, avatar), email, password, sessions (with
    revocation), account & data (export, delete), plus
    Google link status if present — corresponds 1:1 to the
    sections already built on the previous `/account` page,
    including the existing BFF routes
    (`/api/account/profile`, `/api/account/email`,
    `/api/account/password`, `/api/account/sessions`,
    `/api/account/export`, `/api/account/delete`,
    `/api/account/avatar`) — pure UI remapping, no new logic.
  - The exact section order/naming as well as the exact
    opening mechanism (client state vs. intercepting route vs.
    query parameter for deep links) are implementation details, not a
    design point.
  - Replaces the previous standalone `/account` page.

### Auth pages

Five new full-page routes replace the previous auth modal on the
start page (chat remains usable anonymously; "Sign in" in the user area of the
app shell now links to `/login` instead of opening a modal):

| Route | Block template | Note |
|---|---|---|
| `/login` | Split with photo (like `magic-link2`/`reset-password2`) | Email+password, links to forgot password/magic link, "Sign in with Google" |
| `/signup` | `signup2` (centered, logo) | Email+password, link to login |
| `/magic-link` | `magic-link2` (split with photo) | Email field only |
| `/reset-password` | `reset-password2` (split with photo) | Set a new password, replaces the existing route folder |
| `/verify-email` | `verify-email2` layout, **content deviates** | see below |

**Deviation `verify-email2`:** The block is built for a manually
typed 6-digit code. The backend, however, works
token-link based (`GET /v1/accounts/verify-email?token=...`, redeemed automatically
when an email link is opened). Only the
visual split layout is adopted; instead of the code input field, the page shows a
status (confirming… / confirmed / invalid link + resend).
The backend is not changed for this.

All forms continue to use the already existing
auth BFF routes (`/api/auth/login`, `/api/auth/register`,
`/api/auth/magic-link/request` + `/confirm`,
`/api/auth/password-reset/request` + `/confirm`,
`/api/auth/google/login` + `/callback`) — no new backend logic.

### Search & document detail

The existing structure/logic remains unchanged. Only the
components used (Input, Button, Card, Pagination, Badge) and colors switch
to the new theme, and from now on both pages run inside the new
app shell instead of standing alone.

## Data flow

No new backend endpoints. New/changed shadcn/ui dependencies
(`sidebar`, `collapsible`, `dropdown-menu`, `scroll-area`, `separator`,
`label`, `select`, `textarea`, `popover`, possibly `card`) are installed via the
shadcn CLI; the referenced `@shadcnblocks` blocks are fetched via
the same CLI and then adapted to our real data/routes
(the blocks' demo data is replaced completely).

## Error handling

- Auth pages: form validation via `zod` (already part of the blocks);
  existing BFF error responses are shown inline (pattern from the
  previous account page reused).
- `/verify-email`: a missing/invalid/expired token shows an
  explicit error state with a "Resend" option instead of a silent
  failure.
- Profile overlay: the existing error handling per section (e.g.
  sessions list, export) is taken over unchanged, only restyled.

## Test concept

- The existing Playwright E2E suite (`npm run test:e2e`) must be updated for the new
  routes (full-page auth pages instead of a modal, `/account` → overlay,
  `/chats` dropped).
- Visual smoke test per redesigned page after the implementation
  (Playwright screenshot, as already demonstrated in this session against the
  running app), including once in light mode and once in
  dark mode.
- Toggle test: actually operate the light/dark switch once and
  check persistence across a reload (next-themes standard behavior).

## Relation to requirements and ADRs

| Requirement | Relation |
|---|---|
| REQ-UI-001/002 | The chat interface remains a standalone web application, chat-based interaction functionally unchanged, only redesigned. |
| REQ-UI-003 | Citation display/linking in the chat is retained, only visually new. |
| REQ-ACC-* | Chat/search remain usable without an account; auth only becomes more accessible (dedicated pages instead of a modal), no new account requirement. |
| REQ-DIST-003 | Tenant branding infrastructure remains in place, is not wired up in this sub-project — see Open items. |

## Open items / follow-up work

- **Reconnecting tenant branding.** If REQ-DIST-003 is actively
  needed later, `NORMLY_BRAND_COLOR_HSL` must be moved to the new
  `--primary`/`--primary-foreground` variables — deliberately
  not part of this sub-project.
- **Dedicated block layout for search/document detail.** Currently only
  theme adaptation; a dedicated design pass for these two
  pages is a later, separate task.
- **Real notification feature.** The bell in the header is a pure
  placeholder today.
- **Exact opening mechanism of the profile overlay** (client state,
  intercepting route or query parameter for deep links) is decided when
  writing the implementation plan, not here.
- **Exact section order/naming in the profile overlay** is likewise an
  implementation detail.
