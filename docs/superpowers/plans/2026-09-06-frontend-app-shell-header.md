# Frontend App-Shell + Header-Muster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the frontend's single top-nav header (`AppHeader`) with a
collapsible sidebar app-shell (two nav items: Chat, Suche) plus a shared
`PageHeader` pattern (title/subtitle, locale/jurisdiction/theme controls, a
placeholder notification bell), wrapping the Chat, Suche and
Dokument-Detail pages — so the next three plans in this redesign (Chat's
nested sidebar, the Profil-Overlay, the Auth full pages) all build inside
this shell instead of each reinventing page chrome.

**Architecture:** Install only the underlying shadcn/ui primitives the
`@shadcnblocks/application-shell2` block depends on (`sidebar`,
`collapsible`, `dropdown-menu`, `scroll-area`, `separator`, plus
`popover` for the notification bell) via the shadcn CLI, then hand-write a
much simpler `AppShell` component inspired by that block's structure
rather than installing and keeping the block's own generated file — the
demo block ships a workspace switcher, a four-group demo nav, and a
"Support" footer group that the design spec explicitly excludes (see
Global Constraints). Session/logout logic already duplicated once
(`AppHeader`) gets extracted into a shared hook first, so the new
`AppShell`'s user-footer and the still-alive `AppHeader` (kept for pages
this plan doesn't migrate) share one implementation.

**Tech Stack:** Tailwind CSS v3.4 + `tailwindcss-animate` (new dependency
— see Task 1), shadcn/ui primitives via the `@shadcn` default registry
(not `@shadcnblocks` — that registry only hosts full blocks, not base
primitives), existing `next-themes`, `class-variance-authority`,
`lucide-react`, `@radix-ui/react-slot`.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-09-05-frontend-shadcn-redesign-design.md`
  — this plan implements only the "### App-Shell" (lines 78-91) and
  "### Header-Muster" (lines 111-118) sections. It does NOT touch the
  Chat page's nested history sidebar, the Profil-Overlay, the Auth pages,
  or Suche/Dokument-Detail's own content — those are later plans in this
  redesign.
- **No demo nav items.** Per the spec's non-goals, none of
  `application-shell2`'s demo content (Overview/Projects/Team/Workspace
  groups, workspace switcher, "Support" footer group, submenus) survives
  into `AppShell` — exactly two flat nav items, **Chat** and **Suche**.
  This is why Task 1 installs only the block's underlying primitives, not
  the block itself.
- **Two interim decisions, both explicitly temporary — do not treat as
  design gaps to "fix" in this plan:**
  - The `NavUser` dropdown's "Account" item links to the existing
    `/account` page (unchanged). Plan 4 (Profil-Overlay) replaces this
    with an overlay trigger — not this plan's job.
  - When logged out, the sidebar footer renders the existing
    `AuthDialog` component (unchanged modal) instead of a `/login` link.
    Plan 5 (Auth-Seiten) introduces real `/login` etc. pages and updates
    this link then — not this plan's job.
- **`collapsible` and `scroll-area` end up installed but unused by
  `AppShell`'s own code.** The design spec lists them as registry
  dependencies that "must be newly installed" because they're
  `application-shell2`'s own dependencies (for its demo's collapsible
  submenus and long scrollable nav list); our two-flat-item nav needs
  neither. Installing them (Task 1) still satisfies the spec's literal
  requirement — don't force artificial usage into `AppShell` just to
  "use" them.
- **Two known Tailwind-v3-incompatibility traps in canonical shadcn/
  shadcnblocks code, from a hard lesson in the previous plan (Theme-
  Fundament, merged as PR #6) — both apply here, watch for both:**
  1. Tailwind's `/NN` opacity-modifier syntax (`bg-primary/90`) silently
     compiles to nothing when the color token is a bare `var(--x)`
     string. This project's `tailwind.config.ts` already fixed every
     color token this plan touches via its `withOpacity()` helper
     (confirmed by inspecting the actual registry source in advance —
     `sidebar`'s only opacity-modifier use is `text-sidebar-foreground/70`,
     `application-shell2`'s is `bg-muted/50`, both already covered) — but
     every task that introduces a NEW opacity-modifier class not listed
     here must still grep the *built* CSS to confirm it compiled (see
     each task's verification step), not just trust a green build.
  2. **New for this plan:** canonical shadcn code sometimes targets
     Tailwind v4's bare arbitrary-property shorthand,
     `w-(--radix-dropdown-menu-trigger-width)` (parens, no brackets) —
     this is invalid syntax under Tailwind v3 and is silently dropped the
     same way. `application-shell2`'s own `NavUser` demo code has exactly
     this class. Task 3 does not copy it — use the v3-safe
     `w-[--radix-dropdown-menu-trigger-width]` bracket form, or drop the
     trigger-width match entirely if a fixed `min-w-56` is enough (Task 3
     does the latter, see its code).
  3. **Also new for this plan:** several of the newly-installed
     primitives (`dropdown-menu`, `tooltip`, `sheet`, and transitively
     `popover`) use `data-[state=open]:animate-in`-style classes, which
     require the `tailwindcss-animate` Tailwind plugin. This project has
     never had it installed (confirmed: the existing `dialog.tsx` predates
     these classes and doesn't use them) — without it, every one of these
     `animate-*`/`fade-*`/`zoom-*`/`slide-*` classes is an unrecognized
     utility name and is silently dropped (functionally harmless — Radix's
     own open/close state still works via plain CSS display — but every
     menu/tooltip/sheet/popover would pop with zero transition). Task 1
     installs and registers the plugin and verifies it compiles.
- **Existing custom `Avatar` component stays, no new one installed.**
  `NavUser` (Task 3) uses the project's own
  `@/components/ui/avatar`'s `Avatar` (the
  `{ avatarDataUrl, firstName, lastName, email, size }` component from
  Plan 1), not the canonical composable `Avatar`/`AvatarImage`/
  `AvatarFallback` trio `application-shell2`'s own demo code uses — this
  project never installs that second, different `Avatar`.
- Every new/modified source file keeps its existing
  `SPDX-License-Identifier: AGPL-3.0-or-later` + copyright header (see any
  file in `frontend/src` for the exact two lines). Files generated
  verbatim by the shadcn CLI (Task 1's installed primitives) are the one
  exception — leave the CLI's own output as-is, don't hand-edit headers
  into generated files.
- Every commit needs a real DCO trailer: `git commit -s` (produces
  `Signed-off-by: normly <anonymous-jw@pm.me>`); if this session's work is
  attributed to Claude, add `Co-Authored-By: Claude Sonnet 5
  <noreply@anthropic.com>` as a **separate** trailer — never a second
  `Signed-off-by` line.
- No direct push to `main` — branch + PR against the `stackit` remote,
  per `CLAUDE.md`. **Before pushing the branch, opening the PR, or asking
  the user to merge it: ask the user for explicit confirmation first** —
  each of those triggers a billed STACKIT CI run, and the user has asked
  to be asked every time, not just informed afterward.
- Tests: Vitest unit tests live in `frontend/tests/unit/*.test.tsx`,
  discovered automatically. Run with `npm test` from `frontend/`.
  Playwright e2e (`npm run test:e2e`) stays out of scope for this plan's
  automated checks (same CI exclusion as the previous plan); this plan
  does not remove or rename any route, so no existing e2e spec needs
  updating as a result of it — manual visual verification is called out
  explicitly where it matters.
- Branch: create `frontend/app-shell-header` off latest `main` (this
  plan's prerequisite, PR #6 / Theme-Fundament, is already merged).

---

### Task 1: Install shadcn primitives + `tailwindcss-animate`

**Files:**
- Create (via CLI): `frontend/src/components/ui/sidebar.tsx`,
  `frontend/src/components/ui/collapsible.tsx`,
  `frontend/src/components/ui/dropdown-menu.tsx`,
  `frontend/src/components/ui/scroll-area.tsx`,
  `frontend/src/components/ui/separator.tsx`,
  `frontend/src/components/ui/popover.tsx`,
  `frontend/src/components/ui/sheet.tsx`,
  `frontend/src/components/ui/tooltip.tsx`,
  `frontend/src/components/ui/skeleton.tsx`,
  `frontend/src/hooks/use-mobile.tsx` (transitive deps of `sidebar`, pulled
  in automatically)
- Modify: `frontend/package.json`, `frontend/package-lock.json` (new
  `@radix-ui/*` runtime deps from the CLI, plus manually-added
  `tailwindcss-animate` dev dep)
- Modify: `frontend/tailwind.config.ts` (register the
  `tailwindcss-animate` plugin)

**Interfaces:**
- Produces: every primitive above, importable at
  `@/components/ui/<name>` with the canonical shadcn API (e.g.
  `Sidebar`, `SidebarProvider`, `SidebarInset`, `SidebarTrigger`, etc. from
  `sidebar.tsx`; `Popover`, `PopoverTrigger`, `PopoverContent` from
  `popover.tsx`) — Task 3 and Task 4 import directly from these.
- Consumes: nothing from earlier tasks (this is the first task).

- [ ] **Step 1: Record pre-install state of the three at-risk files**

`button.tsx`, `input.tsx` and `avatar.tsx` were hand-migrated in the
previous plan (PR #6) and must not be silently reverted by the CLI if it
decides to "update" a shared dependency. Before installing anything:

Run: `cd frontend && git status --porcelain src/components/ui/button.tsx src/components/ui/input.tsx src/components/ui/avatar.tsx`
Expected: empty output (clean working tree for these three files) — this
is the baseline Step 3 compares against.

- [ ] **Step 2: Install the primitives via the shadcn CLI**

Run: `cd frontend && npx shadcn@latest add sidebar collapsible dropdown-menu scroll-area separator popover -y`

This resolves against the CLI's built-in default `@shadcn` registry (not
`@shadcnblocks` — that custom registry, configured in `components.json`,
only serves full blocks like `application-shell2`; unprefixed names
always resolve to the default registry regardless of what custom
registries are configured). `sidebar`'s own dependencies (`button`,
`separator`, `sheet`, `tooltip`, `input`, `use-mobile`, `skeleton`) get
pulled in automatically — expect roughly a dozen new/touched files, not
just the six named on the command line.

- [ ] **Step 3: Verify the three at-risk files were not touched**

Run: `cd frontend && git status --porcelain src/components/ui/button.tsx src/components/ui/input.tsx src/components/ui/avatar.tsx`
Expected: still empty output. If any of the three shows as modified, the
CLI overwrote a hand-migrated file — run
`git checkout -- src/components/ui/<file>.tsx` for each modified one
before continuing, since Plan 1's migration must survive.

- [ ] **Step 4: Add the `tailwindcss-animate` dependency**

Run: `cd frontend && npm install -D tailwindcss-animate@1.0.7`

- [ ] **Step 5: Register the plugin in `tailwind.config.ts`**

Modify `frontend/tailwind.config.ts` — add the import near the top
(after the existing `Config` type import):

```ts
import tailwindcssAnimate from "tailwindcss-animate";
```

and change the `plugins: []` line to:

```ts
  plugins: [tailwindcssAnimate],
```

- [ ] **Step 6: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: succeeds with no PostCSS/Tailwind/TypeScript errors.

- [ ] **Step 7: Verify `tailwindcss-animate`'s utilities actually compiled**

The build succeeding doesn't confirm the plugin's classes exist in the
output — an unrecognized utility is dropped silently either way (that's
exactly the bug this step exists to catch). None of the newly-installed
primitives are imported by any page yet (that's Tasks 3-5), so Tailwind's
content scan won't have found `animate-in` etc. in application code yet —
check the plugin registered correctly by grepping its own generated base
rule instead:

Run: `cd frontend && npm run build && grep -rl "tw-enter-opacity" .next/static/css/*.css`
Expected: at least one match — `tailwindcss-animate` always emits this
custom-property declaration as part of its base layer, independent of
which `animate-*` utility classes any component actually uses, so its
presence confirms the plugin loaded. (Tasks 3-5's own CSS-grep
verification steps confirm the *utility* classes specific components use
once those components exist.)

- [ ] **Step 8: Commit**

```bash
cd frontend
git add -A src/components/ui src/hooks package.json package-lock.json tailwind.config.ts
git commit -s -m "feat(frontend): install sidebar/dropdown/popover shadcn primitives"
```

---

### Task 2: Extract `useAccountSession`, refactor `AppHeader` onto it

**Files:**
- Create: `frontend/src/lib/use-account-session.ts`
- Create: `frontend/tests/unit/use-account-session.test.ts`
- Modify: `frontend/src/components/app-header.tsx`

**Interfaces:**
- Produces: `useAccountSession()` (named export from
  `@/lib/use-account-session`), returning
  `{ account: AccountSummary | null, refreshSession: () => void, logout: () => Promise<void> }`
  — Task 3's `NavUser` consumes this directly.
- Consumes: the existing `AccountSummary` type from
  `@/lib/account-response` (unchanged).

- [ ] **Step 1: Write the failing test for the hook**

Create `frontend/tests/unit/use-account-session.test.ts`:

```ts
// frontend/tests/unit/use-account-session.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAccountSession } from "@/lib/use-account-session";

const originalFetch = global.fetch;

describe("useAccountSession", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("fetches the session on mount and exposes the account", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          account: {
            accountId: "1", email: "a@example.de", firstName: null, lastName: null,
            avatarDataUrl: null,
          },
        }),
      ),
    );
    const { result } = renderHook(() => useAccountSession());
    await waitFor(() => expect(result.current.account?.email).toBe("a@example.de"));
    expect(global.fetch).toHaveBeenCalledWith("/api/auth/session");
  });

  it("clears the account and posts to the logout endpoint", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          account: {
            accountId: "1", email: "a@example.de", firstName: null, lastName: null,
            avatarDataUrl: null,
          },
        }),
      ),
    );
    const { result } = renderHook(() => useAccountSession());
    await waitFor(() => expect(result.current.account).not.toBeNull());

    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    await act(async () => {
      await result.current.logout();
    });
    expect(global.fetch).toHaveBeenCalledWith("/api/auth/logout", { method: "POST" });
    expect(result.current.account).toBeNull();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- use-account-session`
Expected: FAIL — `Cannot find module '@/lib/use-account-session'`.

- [ ] **Step 3: Implement the hook**

Create `frontend/src/lib/use-account-session.ts`:

```ts
// frontend/src/lib/use-account-session.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import type { AccountSummary } from "@/lib/account-response";

export function useAccountSession() {
  const [account, setAccount] = React.useState<AccountSummary | null>(null);

  const refreshSession = React.useCallback(() => {
    fetch("/api/auth/session")
      .then((response) => response.json())
      .then((body: { account: AccountSummary | null }) => setAccount(body.account))
      .catch(() => setAccount(null));
  }, []);

  React.useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  const logout = React.useCallback(async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      setAccount(null);
    }
  }, []);

  return { account, refreshSession, logout };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- use-account-session`
Expected: PASS

- [ ] **Step 5: Refactor `AppHeader` to use the hook**

In `frontend/src/components/app-header.tsx`, replace the import of
`React` usage for session state and the inline `handleLogout` with the
hook. Change:

```tsx
import { AuthDialog } from "@/components/auth/auth-dialog";
```

to add, right after it:

```tsx
import { useAccountSession } from "@/lib/use-account-session";
```

Then replace this whole block:

```tsx
  const { t } = useTranslation();
  const [account, setAccount] = React.useState<AccountSummary | null>(null);

  const refreshSession = React.useCallback(() => {
    fetch("/api/auth/session")
      .then((response) => response.json())
      .then((body: { account: AccountSummary | null }) => setAccount(body.account))
      .catch(() => setAccount(null));
  }, []);

  React.useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  const handleLogout = async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      setAccount(null);
    }
  };
```

with:

```tsx
  const { t } = useTranslation();
  const { account, refreshSession, logout } = useAccountSession();
```

and update the one remaining reference — the button's `onClick={handleLogout}`
becomes `onClick={logout}`. The now-unused `AccountSummary` type import
and `React.useState`/`React.useCallback`/`React.useEffect` usage: leave
the `import * as React from "react"` line (still needed for JSX) and
remove the now-unused `AccountSummary` type import line
(`import type { AccountSummary } from "@/lib/account-response";`) since
nothing in this file references that type directly anymore.

- [ ] **Step 6: Run the existing `AppHeader` suite to confirm no behavior changed**

Run: `cd frontend && npm test -- app-header`
Expected: PASS, all pre-existing test cases unchanged (this is a pure
refactor — the hook's behavior is identical to what was inlined before).

- [ ] **Step 7: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed.

- [ ] **Step 8: Commit**

```bash
cd frontend
git add src/lib/use-account-session.ts tests/unit/use-account-session.test.ts \
  src/components/app-header.tsx
git commit -s -m "refactor(frontend): extract useAccountSession hook from AppHeader"
```

---

### Task 3: `AppShell` component (sidebar, nav, user footer)

**Files:**
- Create: `frontend/src/components/app-shell.tsx`
- Create: `frontend/tests/unit/app-shell.test.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (new `nav.chat`, `nav.search`, `nav.account` keys)

**Interfaces:**
- Consumes: `Sidebar`/`SidebarProvider`/`SidebarInset`/`SidebarTrigger`/
  `SidebarHeader`/`SidebarContent`/`SidebarFooter`/`SidebarGroup`/
  `SidebarGroupContent`/`SidebarMenu`/`SidebarMenuItem`/`SidebarMenuButton`/
  `SidebarRail` from Task 1's `sidebar.tsx`; `DropdownMenu` family from
  Task 1's `dropdown-menu.tsx`; `useAccountSession` from Task 2; the
  existing `Avatar` from `@/components/ui/avatar` and `AuthDialog` from
  `@/components/auth/auth-dialog` (both unchanged).
- Produces: `AppShell` (named export from `@/components/app-shell`),
  props `{ instanceName: string; logoPath: string | null; children: React.ReactNode }`
  — Task 5's three pages import this directly; its prop shape never
  changes later in this redesign (later plans add pages that use it, they
  don't change its signature).

- [ ] **Step 1: Add the new nav/account i18n keys**

In `frontend/src/lib/i18n/de.json`, add a new top-level `"nav"` object
(placed alphabetically among the existing top-level keys, e.g. right
after `"jurisdiction"` if present, otherwise anywhere at the top level —
exact position doesn't matter, `TranslationKey` derives from the object
shape, not key order):

```json
  "nav": {
    "chat": "Chat",
    "search": "Suche",
    "account": "Konto"
  },
```

In `frontend/src/lib/i18n/en.json`, add the mirrored English block in the
same relative position:

```json
  "nav": {
    "chat": "Chat",
    "search": "Search",
    "account": "Account"
  },
```

Both files must stay valid JSON (existing trailing commas / structure —
check the file after editing parses, e.g. `node -e "require('./src/lib/i18n/de.json')"`).

- [ ] **Step 2: Write the failing test for `AppShell`**

Create `frontend/tests/unit/app-shell.test.tsx`:

```tsx
// frontend/tests/unit/app-shell.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { AppShell } from "@/components/app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

const originalFetch = global.fetch;

describe("AppShell", () => {
  beforeEach(() => {
    // jsdom has no matchMedia -- the sidebar primitive's internal
    // useIsMobile() hook calls it on every render.
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders exactly the Chat and Suche nav links, nothing else", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <AppShell instanceName="normly" logoPath={null}>
          <div>content</div>
        </AppShell>
      </LocaleProvider>,
    );
    expect(screen.getByRole("link", { name: "Chat" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Suche" })).toHaveAttribute("href", "/search");
    expect(screen.getAllByRole("link")).toHaveLength(2);
  });

  it("shows the login trigger in the footer when logged out", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <AppShell instanceName="normly" logoPath={null}>
          <div>content</div>
        </AppShell>
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Anmelden" })).toBeInTheDocument(),
    );
  });

  it("shows the account email and a logout item when logged in", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          account: {
            accountId: "1", email: "a@example.de", firstName: null, lastName: null,
            avatarDataUrl: null,
          },
        }),
      ),
    );
    render(
      <LocaleProvider initialLocale="de">
        <AppShell instanceName="normly" logoPath={null}>
          <div>content</div>
        </AppShell>
      </LocaleProvider>,
    );
    await waitFor(() => expect(screen.getByText("a@example.de")).toBeInTheDocument());
  });

  it("renders the children inside the sidebar inset", () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <AppShell instanceName="normly" logoPath={null}>
          <div>page content</div>
        </AppShell>
      </LocaleProvider>,
    );
    expect(screen.getByText("page content")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && npm test -- app-shell`
Expected: FAIL — `Cannot find module '@/components/app-shell'`.

- [ ] **Step 4: Implement `AppShell`**

Create `frontend/src/components/app-shell.tsx`:

```tsx
// frontend/src/components/app-shell.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronsUpDown, LogOut, MessageSquare, Search, User as UserIcon } from "lucide-react";
import { AuthDialog } from "@/components/auth/auth-dialog";
import { Avatar } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { useTranslation } from "@/lib/i18n/provider";
import { useAccountSession } from "@/lib/use-account-session";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

const NAV_ITEMS: Array<{ href: string; labelKey: TranslationKey; icon: typeof MessageSquare }> = [
  { href: "/", labelKey: "nav.chat", icon: MessageSquare },
  { href: "/search", labelKey: "nav.search", icon: Search },
];

function NavUser() {
  const { t } = useTranslation();
  const { account, refreshSession, logout } = useAccountSession();

  if (!account) {
    return (
      <div className="p-2 group-data-[collapsible=icon]:hidden">
        <AuthDialog onAuthenticated={refreshSession} />
      </div>
    );
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg">
              <Avatar
                avatarDataUrl={account.avatarDataUrl}
                firstName={account.firstName}
                lastName={account.lastName}
                email={account.email}
              />
              <span className="truncate text-sm text-muted-foreground">{account.email}</span>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          {/* Fixed min-w-56 instead of matching the trigger's width: the
              canonical block uses Tailwind v4's `w-(--radix-...)` bare
              arbitrary-property shorthand, invalid syntax under this
              project's Tailwind v3 (silently dropped, same as the
              opacity-modifier trap -- see Global Constraints). */}
          <DropdownMenuContent className="min-w-56 rounded-lg" side="top" align="end">
            <DropdownMenuLabel className="font-normal">{account.email}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {/* Interim: links to the existing standalone /account page.
                Plan 4 (Profil-Overlay) replaces this with an overlay
                trigger -- not this plan's job, see Global Constraints. */}
            <DropdownMenuItem asChild>
              <Link href="/account">
                <UserIcon className="mr-2 size-4" />
                {t("nav.account")}
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout}>
              <LogOut className="mr-2 size-4" />
              {t("auth.logoutButton")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}

export function AppShell({
  instanceName,
  logoPath,
  children,
}: {
  instanceName: string;
  logoPath: string | null;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { t } = useTranslation();

  return (
    <SidebarProvider>
      <Sidebar variant="inset" collapsible="icon">
        <SidebarHeader>
          <div className="flex items-center gap-2 px-2 py-1 group-data-[collapsible=icon]:flex-col">
            {logoPath ? (
              <img src={logoPath} alt={instanceName} className="h-6" />
            ) : (
              <span className="truncate font-semibold group-data-[collapsible=icon]:hidden">
                {instanceName}
              </span>
            )}
            <SidebarTrigger className="ml-auto group-data-[collapsible=icon]:ml-0" />
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {NAV_ITEMS.map(({ href, labelKey, icon: Icon }) => (
                  <SidebarMenuItem key={href}>
                    <SidebarMenuButton asChild isActive={pathname === href} tooltip={t(labelKey)}>
                      <Link href={href}>
                        <Icon className="size-4" />
                        <span>{t(labelKey)}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter>
          <NavUser />
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>
      <SidebarInset>{children}</SidebarInset>
    </SidebarProvider>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- app-shell`
Expected: PASS

- [ ] **Step 6: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed.

- [ ] **Step 7: Grep the built CSS for this task's opacity-modifier classes**

`NavUser`'s avatar fallback and the sidebar primitives introduce no new
opacity-modifier classes beyond the ones already confirmed safe in Global
Constraints (`text-sidebar-foreground/70`, `bg-muted/50`) — this step
exists to catch any this plan's author missed, not to re-confirm known-good
ones.

Run: `cd frontend && npm run build && grep -c "sidebar-foreground" .next/static/css/*.css`
Expected: a non-zero count (the sidebar primitive's own classes compiled).

- [ ] **Step 8: Commit**

```bash
cd frontend
git add src/components/app-shell.tsx tests/unit/app-shell.test.tsx \
  src/lib/i18n/de.json src/lib/i18n/en.json
git commit -s -m "feat(frontend): add AppShell sidebar with Chat/Suche nav and user footer"
```

---

### Task 4: `PageHeader` component (title, controls, notification bell)

**Files:**
- Create: `frontend/src/components/page-header.tsx`
- Create: `frontend/tests/unit/page-header.test.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (new `nav.notificationsLabel`, `nav.noNotifications` keys)

**Interfaces:**
- Consumes: `Popover`/`PopoverTrigger`/`PopoverContent` from Task 1's
  `popover.tsx`; the existing `ModeToggle`, `LocaleSwitcher`,
  `JurisdictionSwitcher`, `Button` (all unchanged).
- Produces: `PageHeader` (named export from `@/components/page-header`),
  props `{ titleKey: TranslationKey; subtitleKey?: TranslationKey }` —
  Task 5's three pages use this; later plans (Chat, Profil-Overlay pages)
  reuse the same component and prop shape.

- [ ] **Step 1: Add the notification-bell i18n keys**

In `frontend/src/lib/i18n/de.json`, extend the `"nav"` object added in
Task 3 with two more keys (same object, not a new one):

```json
  "nav": {
    "chat": "Chat",
    "search": "Suche",
    "account": "Konto",
    "notificationsLabel": "Benachrichtigungen",
    "noNotifications": "Keine neuen Benachrichtigungen"
  },
```

In `frontend/src/lib/i18n/en.json`:

```json
  "nav": {
    "chat": "Chat",
    "search": "Search",
    "account": "Account",
    "notificationsLabel": "Notifications",
    "noNotifications": "No new notifications"
  },
```

- [ ] **Step 2: Write the failing test for `PageHeader`**

Create `frontend/tests/unit/page-header.test.tsx`:

```tsx
// frontend/tests/unit/page-header.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { JurisdictionProvider } from "@/lib/jurisdiction/provider";
import { PageHeader } from "@/components/page-header";

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light", setTheme: vi.fn() }),
}));

describe("PageHeader", () => {
  it("renders the translated title", () => {
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <PageHeader titleKey="nav.chat" />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    expect(screen.getByRole("heading", { name: "Chat" })).toBeInTheDocument();
  });

  it("renders no subtitle when subtitleKey is omitted", () => {
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <PageHeader titleKey="nav.chat" />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    expect(screen.queryByText("Konto")).not.toBeInTheDocument();
  });

  it("shows the static no-notifications message in the bell popover", () => {
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <PageHeader titleKey="nav.chat" />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Benachrichtigungen" }));
    expect(screen.getByText("Keine neuen Benachrichtigungen")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && npm test -- page-header`
Expected: FAIL — `Cannot find module '@/components/page-header'`.

- [ ] **Step 4: Implement `PageHeader`**

Create `frontend/src/components/page-header.tsx`:

```tsx
// frontend/src/components/page-header.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { JurisdictionSwitcher } from "@/components/jurisdiction-switcher";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { ModeToggle } from "@/components/mode-toggle";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useTranslation } from "@/lib/i18n/provider";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

export function PageHeader({
  titleKey,
  subtitleKey,
}: {
  titleKey: TranslationKey;
  subtitleKey?: TranslationKey;
}) {
  const { t } = useTranslation();

  return (
    <header className="flex items-center justify-between gap-4 border-b p-4">
      <div>
        <h1 className="text-lg font-semibold">{t(titleKey)}</h1>
        {subtitleKey && <p className="text-sm text-muted-foreground">{t(subtitleKey)}</p>}
      </div>
      <div className="flex items-center gap-2">
        <LocaleSwitcher />
        <JurisdictionSwitcher />
        <ModeToggle />
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size="icon" aria-label={t("nav.notificationsLabel")}>
              <Bell className="h-4 w-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end">
            <p className="text-sm text-muted-foreground">{t("nav.noNotifications")}</p>
          </PopoverContent>
        </Popover>
      </div>
    </header>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- page-header`
Expected: PASS

- [ ] **Step 6: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed.

- [ ] **Step 7: Grep the built CSS for the popover's classes**

`popover.tsx`'s `PopoverContent` uses `bg-popover`/`text-popover-foreground`
(already-covered tokens per Global Constraints) plus
`data-[state=open]:animate-in` (needs Task 1's plugin).

Run: `cd frontend && npm run build && grep -c "bg-popover\|animate-in" .next/static/css/*.css`
Expected: a non-zero count.

- [ ] **Step 8: Commit**

```bash
cd frontend
git add src/components/page-header.tsx tests/unit/page-header.test.tsx \
  src/lib/i18n/de.json src/lib/i18n/en.json
git commit -s -m "feat(frontend): add PageHeader with theme/locale controls and notification bell"
```

---

### Task 5: Wire `AppShell` + `PageHeader` into Chat, Suche, Dokument-Detail

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/app/search/page.tsx`
- Modify: `frontend/src/app/documents/[id]/page.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (one new `nav.documentDetailTitle` key)

**Interfaces:**
- Consumes: `AppShell` (Task 3), `PageHeader` (Task 4).
- Produces: nothing new — this task only rewires existing pages.

Three pages currently each render `<AppHeader instanceName={...} logoPath={...} />`
directly above their content. `account/page.tsx`, `chats/page.tsx`,
`confirm-email-change/page.tsx` and `reset-password/page.tsx` keep using
the unmodified `AppHeader` — they're out of scope (see Global
Constraints: Plan 3 rebuilds the chat page and retires `/chats`, Plan 4
retires the standalone `/account` page, Plan 5 replaces
`reset-password`/adds new auth pages entirely).

- [ ] **Step 1: Add the document-detail title key**

In `frontend/src/lib/i18n/de.json`, extend the `"nav"` object once more:

```json
    "noNotifications": "Keine neuen Benachrichtigungen",
    "documentDetailTitle": "Dokument"
```

(i.e. add `documentDetailTitle` as the new last entry in the object built
across Tasks 3-4). In `frontend/src/lib/i18n/en.json`:

```json
    "noNotifications": "No new notifications",
    "documentDetailTitle": "Document"
```

The actual document number/title continues to render inside
`DocumentDetailContent` exactly as before (unchanged) — this key is only
for the generic page-chrome title above it, per the spec's explicit
non-goal of a new document-detail layout.

- [ ] **Step 2: Rewrite `page.tsx` (Chat/home)**

Replace `frontend/src/app/page.tsx`'s entire content:

```tsx
// frontend/src/app/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { HomePageContent } from "./home-page-content";

export default function HomePage() {
  const config = getInstanceConfig();
  return (
    <AppShell instanceName={config.instanceName} logoPath={config.logoPath}>
      <PageHeader titleKey="nav.chat" />
      <HomePageContent />
    </AppShell>
  );
}
```

- [ ] **Step 3: Rewrite `search/page.tsx`**

Replace `frontend/src/app/search/page.tsx`'s entire content:

```tsx
// frontend/src/app/search/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { SearchPageContent } from "./search-page-content";

export default function SearchPage() {
  const config = getInstanceConfig();
  return (
    <AppShell instanceName={config.instanceName} logoPath={config.logoPath}>
      <PageHeader titleKey="nav.search" />
      <main className="mx-auto max-w-2xl p-4">
        <SearchPageContent />
      </main>
    </AppShell>
  );
}
```

- [ ] **Step 4: Rewrite `documents/[id]/page.tsx`**

Replace `frontend/src/app/documents/[id]/page.tsx`'s entire content:

```tsx
// frontend/src/app/documents/[id]/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { DocumentDetailContent } from "./document-detail-content";

export default function DocumentDetailPage({ params }: { params: { id: string } }) {
  const config = getInstanceConfig();
  return (
    <AppShell instanceName={config.instanceName} logoPath={config.logoPath}>
      <PageHeader titleKey="nav.documentDetailTitle" />
      <main className="mx-auto max-w-2xl p-4">
        <DocumentDetailContent documentId={params.id} />
      </main>
    </AppShell>
  );
}
```

- [ ] **Step 5: Run the full unit suite**

Run: `cd frontend && npm test`
Expected: PASS, every suite — nothing in `tests/unit` directly renders
these three page components (they're server components composing client
ones already covered by their own tests), so no existing test needs
updating for this step.

- [ ] **Step 6: Run the build**

Run: `cd frontend && npm run build`
Expected: succeeds, all three routes (`/`, `/search`,
`/documents/[id]`) build without error.

- [ ] **Step 7: Grep the built CSS for anything this task's own JSX introduces**

This task's new JSX (`<main className="mx-auto max-w-2xl p-4">`) uses no
opacity-modifier or animate classes of its own — nothing new to verify
beyond Tasks 1/3/4's checks. Run the combined check once more as a final
gate before the manual pass:

Run: `cd frontend && npm run build && grep -c "sidebar-foreground\|bg-popover\|animate-in\|tw-enter-opacity" .next/static/css/*.css`
Expected: a non-zero count (all four families present in the final,
fully-wired build).

- [ ] **Step 8: Manual visual check**

Start the app (`npm run dev`, rebuilding the sandbox stack from scratch if
needed — Postgres container, the three `uvicorn` processes, `npm run dev`;
see this redesign's project memory for the exact commands, the previous
sandbox was torn down). In a browser, confirm on `/`, `/search`, and a
`/documents/<id>` page (needs at least one ingested document):
- The sidebar renders with exactly two items, "Chat" and "Suche", the
  active one highlighted for the current page.
- Collapsing the sidebar (the trigger button) shrinks it to icon-only and
  back.
- Logged out: the sidebar footer shows an "Anmelden" button that opens
  the existing auth dialog; logging in updates the footer to show the
  avatar + email.
- Logged in: clicking the user footer opens a dropdown with "Konto" (still
  linking to the old `/account` page) and "Abmelden" (actually logs out).
- The page header shows the right title ("Chat" / "Suche" / "Dokument"),
  and its locale/jurisdiction/theme/bell controls all still work — the
  bell popover shows "Keine neuen Benachrichtigungen".
- Toggle dark mode: sidebar, dropdown, and popover all render correctly
  in dark mode too (not just the page body).

- [ ] **Step 9: Commit**

```bash
cd frontend
git add src/app/page.tsx src/app/search/page.tsx src/app/documents/\[id\]/page.tsx \
  src/lib/i18n/de.json src/lib/i18n/en.json
git commit -s -m "feat(frontend): wrap Chat, Suche and Dokument-Detail in AppShell"
```

---

## After This Plan

Ask the user for explicit confirmation before pushing the branch and
before opening a PR (each triggers a billed STACKIT CI run — see Global
Constraints). Once confirmed: push `frontend/app-shell-header`, open a PR
against `main` on the `stackit` remote, wait for the CI pipeline's
`test-frontend` job to go green, then ask the user to merge (same
confirm-first rule applies to the merge trigger). The next plan in this
redesign (Chat-Seite's nested history sidebar, per
`docs/superpowers/specs/2026-09-05-frontend-shadcn-redesign-design.md`)
depends on this one being merged first.
