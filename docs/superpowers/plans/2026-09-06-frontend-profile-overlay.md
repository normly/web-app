# Frontend Profil-Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the standalone `/account` page with a small, geblurrtes
Dialog-Overlay (Claude-style: bounded width/height, backdrop-blur, opened
from the sidebar's user menu, not a full page) — reusing the six already-
built account sections unchanged, just reorganized behind a left-nav
switcher instead of one long scroll.

**Architecture:** A new `ProfileOverlay` component wraps the existing
`Dialog`/`DialogContent` primitive (Plan 1) with a `settings-profile4`-
style two-column layout (icon-less text nav on the left, one active
section's content on the right) — adapted, not installed verbatim: the
block's own demo fields (Bio/Social-Links/Timezone) and its third-party
`diceui` file-upload dependency are dropped entirely, since the real
avatar upload already exists in `NameAvatarSection`. `useAccountSession`
(Plan 2) gains one small addition (`setAccount`) so section components'
existing `onAccountUpdated` callbacks can update the shared session state
directly, instead of re-fetching from the server after every edit.

**Tech Stack:** Existing `Dialog`/`DialogContent`/`DialogTitle` (Plan 1),
`useAccountSession` (Plan 2) — no new shadcn primitives, no new
dependencies.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-09-05-frontend-shadcn-redesign-design.md`
  — this plan implements only the "### Profil-Overlay" section (lines
  120-142). It does NOT touch `AppShell`'s Chat/Suche nav, `PageHeader`,
  the chat page, or auth pages — those are other plans.
- **Reuse the six existing account sections completely unchanged.**
  `NameAvatarSection`, `EmailSection`, `PasswordSection`,
  `SessionsSection`, `ExportSection`, `DeleteAccountSection` (all in
  `frontend/src/components/account/`) already have their own heading,
  form, save action, and BFF-route calls (`/api/account/profile`,
  `/api/account/email`, `/api/account/password`, `/api/account/sessions`,
  `/api/account/export`, `/api/account/delete`, `/api/account/avatar`).
  This plan is "reines UI-Remapping, keine neue Logik" per the spec — no
  task touches these six files' internals, only Task 1's narrow
  color-token fix (see below).
- **No Google-link section.** The spec says "plus Google-Verknüpfungsstatus
  falls vorhanden" — no such section exists anywhere in this codebase
  today (confirmed: `grep -rli google frontend/src/components/account`
  finds nothing), so there is nothing to include. Do not build one; that
  would be new scope this plan doesn't own.
- **No `settings-profile4` demo fields.** Bio, Social Links, Phone,
  Location, Website, Timezone, Language — none of these exist in this
  app's account model and none should be added. The block is a *layout*
  reference only (left-nav + content-card two-column pattern), the same
  way `ai-chat-v2` was structural-reference-only for the chat page in an
  earlier plan.
- **No shared "Speichern"-Leiste (bottom save bar).** The spec describes
  `settings-profile4`'s own structure as including one, but each of the
  six existing account sections already has its own inline save button
  tied to its own already-working handler — there is no single unified
  "save everything" action to hook a shared bar to, and inventing one
  would be new logic, contradicting the spec's own "keine neue Logik"
  instruction for this plan. Each section keeps saving itself
  independently, exactly as it does today.
- **No `diceui` file-upload dependency.** `settings-profile4`'s own avatar
  upload uses a third-party `@/components/diceui/file-upload` registry
  item (`https://diceui.com/r/file-upload.json`) for drag-and-drop —
  `NameAvatarSection` already has its own working upload UI (a plain
  file `<input>`) using the real `/api/account/avatar` route. Do not
  install or reference the diceui component anywhere.
- **Exactly two nav groups become one: "Konto & Daten" combines Export and
  Delete-Account** under a single left-nav entry, per the spec's own
  section list ("Profil (Name, Avatar), E-Mail, Passwort, Sitzungen (mit
  Widerruf), Konto & Daten (Export, Löschen)") — five nav items total,
  not six.
- **Opening mechanism is client state, not a route.** The spec explicitly
  leaves this as an implementation detail. This plan's choice: `AppShell`
  (Plan 2) owns an `open`/`onOpenChange` boolean and renders
  `<ProfileOverlay>` as a sibling of its `Sidebar`; `NavUser`'s "Account"
  dropdown item becomes a button that flips it to `true`, instead of a
  `<Link href="/account">`.
- Every new/modified hand-written source file keeps the
  `SPDX-License-Identifier: AGPL-3.0-or-later` + copyright header.
- Every commit needs `git commit -s` (DCO `Signed-off-by: normly
  <anonymous-jw@pm.me>`) plus a separate `Co-Authored-By: Claude Sonnet 5
  <noreply@anthropic.com>` trailer for AI-executed work — never a second
  `Signed-off-by` line.
- No direct push to `main` — branch + PR against the `stackit` remote.
  **Ask the user for explicit confirmation before pushing the branch,
  opening the PR, or asking them to merge it** — each triggers a billed
  STACKIT CI run, and the user has asked to be asked every time.
- Tests: Vitest unit tests in `frontend/tests/unit/*.test.tsx`, run with
  `npm test` from `frontend/`. Playwright e2e stays out of scope for this
  plan's automated checks (same exclusion as Plans 1-3); this plan removes
  the `/account` route, which likely affects an existing e2e spec — flag
  it as a manual follow-up in the PR description, not fixed here (same
  pattern as the `/chats` retirement in the prior plan).
- Branch: create `frontend/profile-overlay` off latest `main` (Plans 1-3
  are already merged).

---

### Task 1: Migrate account sections off the raw `red-600` color

**Files:**
- Modify: `frontend/src/components/account/name-avatar-section.tsx`
- Modify: `frontend/src/components/account/email-section.tsx`
- Modify: `frontend/src/components/account/password-section.tsx`
- Modify: `frontend/src/components/account/sessions-section.tsx`
- Modify: `frontend/src/components/account/delete-account-section.tsx`

**Interfaces:**
- Consumes: nothing new — no prop shape of any of these five components
  changes.
- Produces: nothing new for later tasks; this is a values-only visual fix,
  parked explicitly in Plan 1's review ("~12 pre-existing pages use
  `text-red-600` for errors, under WCAG AA contrast against the new dark
  background... belongs to each page's own later redesign plan") — this
  plan is that redesign for the account sections.

All nine occurrences are error/destructive text, one destructive border,
and one destructive button — every one has a real, already-`withOpacity()`-
covered token to replace it, from Plan 1's `tailwind.config.ts`.

- [ ] **Step 1: Replace the five plain-text/border occurrences**

In each of the five files below, change every `text-red-600` (in error
`<p>`/`<button>` elements) to `text-destructive`, and (in
`delete-account-section.tsx` only) `border-red-600` to
`border-destructive`:

`frontend/src/components/account/name-avatar-section.tsx` — three
occurrences: line with `className="text-sm text-red-600 underline"` (the
"remove avatar" button) → `className="text-sm text-destructive underline"`;
the two `<p className="text-sm text-red-600">` error messages (avatar
update error, save-name error) → `<p className="text-sm text-destructive">`.

`frontend/src/components/account/email-section.tsx` — one occurrence:
`<p className="text-sm text-red-600">{t("account.emailChangeGenericError")}</p>`
→ `<p className="text-sm text-destructive">...`.

`frontend/src/components/account/password-section.tsx` — one occurrence:
`<p className="text-sm text-red-600">{t("account.passwordChangeError")}</p>`
→ `<p className="text-sm text-destructive">...`.

`frontend/src/components/account/sessions-section.tsx` — two occurrences:
both `<p className="text-sm text-red-600">` (sessions-load error,
session-revoke error) → `<p className="text-sm text-destructive">`.

`frontend/src/components/account/delete-account-section.tsx` — three
occurrences:
- `<section className="flex flex-col gap-3 rounded border border-red-600 p-4">`
  → `<section className="flex flex-col gap-3 rounded border border-destructive p-4">`
- `<h2 className="text-lg font-semibold text-red-600">` → `<h2 className="text-lg font-semibold text-destructive">`
- `<p className="text-sm text-red-600">{t("account.deleteAccountError")}</p>`
  → `<p className="text-sm text-destructive">...`

- [ ] **Step 2: Replace the one hardcoded destructive button**

In `frontend/src/components/account/delete-account-section.tsx`, replace:

```tsx
        <Button
          type="submit" disabled={!canDelete || isSubmitting}
          className="self-start bg-red-600 text-white hover:bg-red-700"
        >
```

with:

```tsx
        <Button
          type="submit" disabled={!canDelete || isSubmitting}
          variant="destructive" className="self-start"
        >
```

(`Button`'s `variant="destructive"` already exists, from Plan 1's
migration — `bg-destructive text-destructive-foreground
hover:bg-destructive/90` — no need for hardcoded colors anymore.)

- [ ] **Step 3: Run the existing tests that cover these components**

Run: `cd frontend && npm test -- account`
Expected: PASS — `account-page.test.tsx` and `delete-account-section.test.tsx`
check rendered text/behavior, not classes, so this is a safe,
behavior-preserving change.

- [ ] **Step 4: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed.

- [ ] **Step 5: Commit**

```bash
cd frontend
git add src/components/account/name-avatar-section.tsx \
  src/components/account/email-section.tsx src/components/account/password-section.tsx \
  src/components/account/sessions-section.tsx src/components/account/delete-account-section.tsx
git commit -s -m "refactor(frontend): migrate account sections off raw red-600 to the destructive token"
```

---

### Task 2: `ProfileOverlay` component

**Files:**
- Modify: `frontend/src/lib/use-account-session.ts`
- Modify: `frontend/tests/unit/use-account-session.test.ts`
- Create: `frontend/src/components/account/profile-overlay.tsx`
- Create: `frontend/tests/unit/profile-overlay.test.tsx`
- Modify: `frontend/src/components/ui/dialog.tsx`
- Modify: `frontend/src/lib/i18n/de.json`, `frontend/src/lib/i18n/en.json`
  (new `account.dataSectionTitle` key)

**Interfaces:**
- Consumes: `useAccountSession()` (extended in this task, see below);
  `Dialog`/`DialogContent`/`DialogTitle` (extended in this task);
  `NameAvatarSection`/`EmailSection`/`PasswordSection`/`SessionsSection`/
  `ExportSection`/`DeleteAccountSection` (Task 1, unchanged prop shapes).
- Produces: `useAccountSession()` now also returns `setAccount:
  React.Dispatch<React.SetStateAction<AccountSummary | null>>` — a strict
  addition, existing callers (`AppHeader`, `AppShell`'s `NavUser`)
  destructure only the fields they already use and are unaffected.
  `ProfileOverlay` (named export from `@/components/account/profile-overlay`),
  props `{ open: boolean; onOpenChange: (open: boolean) => void }` — Task 3
  wires this into `AppShell`.

- [ ] **Step 1: Add the combined-section i18n key**

In `frontend/src/lib/i18n/de.json`, add to the existing `"account"`
object:

```json
    "dataSectionTitle": "Konto & Daten"
```

In `frontend/src/lib/i18n/en.json`:

```json
    "dataSectionTitle": "Account & Data"
```

- [ ] **Step 2: Write the failing test for `useAccountSession`'s new `setAccount`**

Add to `frontend/tests/unit/use-account-session.test.ts` (new `it` block,
inside the existing `describe`, after the existing two tests):

```ts
  it("exposes a setter that updates the account without a network call", async () => {
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

    const fetchCallsBefore = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.length;
    act(() => {
      result.current.setAccount((current) => (current ? { ...current, firstName: "Alex" } : current));
    });
    expect(result.current.account?.firstName).toBe("Alex");
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(fetchCallsBefore);
  });
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && npm test -- use-account-session`
Expected: FAIL — `result.current.setAccount` is `undefined`, calling it
throws.

- [ ] **Step 4: Add `setAccount` to the hook's return value**

In `frontend/src/lib/use-account-session.ts`, change the final `return`
statement from:

```ts
  return { account, refreshSession, logout };
```

to:

```ts
  return { account, refreshSession, logout, setAccount };
```

(`setAccount` is already the `React.useState` setter defined at the top
of the hook — this is a one-line addition, nothing else in the file
changes.)

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- use-account-session`
Expected: PASS, all 3 tests.

- [ ] **Step 6: Add `backdrop-blur-sm` to the shared dialog overlay**

In `frontend/src/components/ui/dialog.tsx`, change `DialogOverlay`'s
className from:

```tsx
    className={cn("fixed inset-0 z-50 bg-black/50", className)}
```

to:

```tsx
    className={cn("fixed inset-0 z-50 bg-black/50 backdrop-blur-sm", className)}
```

(This affects every `Dialog` in the app, including the existing
`AuthDialog` — a deliberate, low-risk shared improvement matching the
spec's "geblurrter Hintergrund... ähnlich dem bisherigen Auth-Modal, nur
größer," which reads as the auth modal keeping the same overlay treatment,
just newly blurred, not as something scoped only to the profile overlay.)

- [ ] **Step 7: Write the failing tests for `ProfileOverlay`**

Create `frontend/tests/unit/profile-overlay.test.tsx`:

```tsx
// frontend/tests/unit/profile-overlay.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ProfileOverlay } from "@/components/account/profile-overlay";

const originalFetch = global.fetch;

function renderOverlay(open = true) {
  return render(
    <LocaleProvider initialLocale="de">
      <ProfileOverlay open={open} onOpenChange={vi.fn()} />
    </LocaleProvider>,
  );
}

describe("ProfileOverlay", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the login-required message when there is no session", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    renderOverlay();
    await waitFor(() =>
      expect(screen.getByText("Melde dich an, um dein Konto zu verwalten.")).toBeInTheDocument(),
    );
  });

  it("shows the login-required message when the session fetch rejects", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("network error"));
    renderOverlay();
    await waitFor(() =>
      expect(screen.getByText("Melde dich an, um dein Konto zu verwalten.")).toBeInTheDocument(),
    );
  });

  it("renders the profile section by default once a session is found", async () => {
    global.fetch = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/account/sessions")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            account: {
              accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
              avatarDataUrl: null,
            },
          }),
        ),
      );
    });
    renderOverlay();
    await waitFor(() => expect(screen.getByText("Name und Profilbild")).toBeInTheDocument());
    expect(screen.queryByText("E-Mail-Adresse")).not.toBeInTheDocument();
  });

  it("switches to the email section when its nav item is clicked", async () => {
    global.fetch = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/account/sessions")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            account: {
              accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
              avatarDataUrl: null,
            },
          }),
        ),
      );
    });
    renderOverlay();
    await waitFor(() => expect(screen.getByText("Name und Profilbild")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "E-Mail-Adresse" }));
    expect(screen.getByText("Aktuelle E-Mail-Adresse")).toBeInTheDocument();
    expect(screen.queryByText("Name und Profilbild")).not.toBeInTheDocument();
  });

  it("shows the combined Konto & Daten nav item leading to both Export and Delete sections", async () => {
    global.fetch = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/account/sessions")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            account: {
              accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
              avatarDataUrl: null, hasPassword: true,
            },
          }),
        ),
      );
    });
    renderOverlay();
    await waitFor(() => expect(screen.getByText("Name und Profilbild")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Konto & Daten" }));
    expect(screen.getByText("Daten exportieren")).toBeInTheDocument();
    expect(screen.getByText("Konto löschen")).toBeInTheDocument();
  });
});
```

- [ ] **Step 8: Run it to verify it fails**

Run: `cd frontend && npm test -- profile-overlay`
Expected: FAIL — `Cannot find module '@/components/account/profile-overlay'`.

- [ ] **Step 9: Implement `ProfileOverlay`**

Create `frontend/src/components/account/profile-overlay.tsx`:

```tsx
// frontend/src/components/account/profile-overlay.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { NameAvatarSection } from "@/components/account/name-avatar-section";
import { EmailSection } from "@/components/account/email-section";
import { PasswordSection } from "@/components/account/password-section";
import { SessionsSection } from "@/components/account/sessions-section";
import { ExportSection } from "@/components/account/export-section";
import { DeleteAccountSection } from "@/components/account/delete-account-section";
import { useAccountSession } from "@/lib/use-account-session";
import { useTranslation } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

type SectionId = "profile" | "email" | "password" | "sessions" | "data";

const SECTIONS: { id: SectionId; labelKey: TranslationKey }[] = [
  { id: "profile", labelKey: "account.nameAvatarTitle" },
  { id: "email", labelKey: "account.emailTitle" },
  { id: "password", labelKey: "account.passwordTitle" },
  { id: "sessions", labelKey: "account.sessionsTitle" },
  { id: "data", labelKey: "account.dataSectionTitle" },
];

export function ProfileOverlay({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const { account, setAccount } = useAccountSession();
  const [activeSection, setActiveSection] = React.useState<SectionId>("profile");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogTitle>{t("account.pageTitle")}</DialogTitle>
        {!account ? (
          <p className="text-sm text-muted-foreground">{t("account.loginRequired")}</p>
        ) : (
          <div className="flex flex-col gap-6 sm:flex-row">
            <nav className="flex shrink-0 flex-row gap-1 overflow-x-auto sm:w-40 sm:flex-col sm:overflow-visible">
              {SECTIONS.map((section) => (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => setActiveSection(section.id)}
                  className={cn(
                    "whitespace-nowrap rounded-md px-3 py-2 text-left text-sm transition-colors",
                    activeSection === section.id
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  {t(section.labelKey)}
                </button>
              ))}
            </nav>
            <div className="max-h-[60vh] min-w-0 flex-1 overflow-y-auto">
              {activeSection === "profile" && (
                <NameAvatarSection account={account} onAccountUpdated={setAccount} />
              )}
              {activeSection === "email" && <EmailSection account={account} />}
              {activeSection === "password" && <PasswordSection />}
              {activeSection === "sessions" && <SessionsSection />}
              {activeSection === "data" && (
                <div className="flex flex-col gap-6">
                  <ExportSection />
                  <DeleteAccountSection account={account} />
                </div>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

(`onAccountUpdated={setAccount}` works directly: `NameAvatarSection`'s
prop type is `(account: AccountSummary) => void`, and passing the raw
`React.Dispatch<SetStateAction<AccountSummary | null>>` setter satisfies
that — calling `setAccount(newAccount)` matches the setter's
value-argument overload exactly.)

- [ ] **Step 10: Run the test to verify it passes**

Run: `cd frontend && npm test -- profile-overlay`
Expected: PASS, all 5 tests.

- [ ] **Step 11: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed.

- [ ] **Step 12: Commit**

```bash
cd frontend
git add src/lib/use-account-session.ts tests/unit/use-account-session.test.ts \
  src/components/account/profile-overlay.tsx tests/unit/profile-overlay.test.tsx \
  src/components/ui/dialog.tsx src/lib/i18n/de.json src/lib/i18n/en.json
git commit -s -m "feat(frontend): add ProfileOverlay dialog with section switcher"
```

---

### Task 3: Wire `ProfileOverlay` into `AppShell`

**Files:**
- Modify: `frontend/src/components/app-shell.tsx`
- Modify: `frontend/tests/unit/app-shell.test.tsx`

**Interfaces:**
- Consumes: `ProfileOverlay` (Task 2).
- Produces: nothing new — `AppShell`'s own props (`{ instanceName,
  logoPath, children }`) are unchanged; this task only rewires what its
  "Account" menu item does internally.

- [ ] **Step 1: Write the failing test for the overlay trigger**

Add to `frontend/tests/unit/app-shell.test.tsx` (new `it` block, inside
the existing `describe("AppShell", ...)`, after the existing tests):

```tsx
  it("opens the profile overlay instead of navigating when Konto is clicked", async () => {
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
    fireEvent.click(screen.getByRole("button", { name: "a@example.de" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Konto" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Konto" })).not.toBeInTheDocument();
  });
```

Add `fireEvent` to the existing `import { render, screen, waitFor } from
"@testing-library/react";` line if not already present.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- app-shell`
Expected: FAIL — clicking "Konto" currently navigates via a `<Link>`, no
`role="dialog"` appears.

- [ ] **Step 3: Rewire `NavUser`'s "Account" item and mount `ProfileOverlay`**

In `frontend/src/components/app-shell.tsx`, add the import:

```tsx
import { ProfileOverlay } from "@/components/account/profile-overlay";
```

Change `NavUser`'s signature from `function NavUser()` to accept the
open-callback:

```tsx
function NavUser({ onOpenProfile }: { onOpenProfile: () => void }) {
```

Replace this block inside `NavUser`:

```tsx
            {/* Interim: links to the existing standalone /account page.
                Plan 4 (Profil-Overlay) replaces this with an overlay
                trigger -- not this plan's job, see Global Constraints. */}
            <DropdownMenuItem asChild>
              <Link href="/account">
                <UserIcon className="mr-2 size-4" />
                {t("nav.account")}
              </Link>
            </DropdownMenuItem>
```

with:

```tsx
            <DropdownMenuItem onClick={onOpenProfile}>
              <UserIcon className="mr-2 size-4" />
              {t("nav.account")}
            </DropdownMenuItem>
```

Then, in `AppShell` itself, add the open-state and pass it down, and
mount `ProfileOverlay` as a sibling of `Sidebar`:

```tsx
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
  const [profileOpen, setProfileOpen] = React.useState(false);

  return (
    <SidebarProvider>
      <Sidebar variant="inset" collapsible="icon">
        {/* ...unchanged... */}
        <SidebarFooter>
          <NavUser onOpenProfile={() => setProfileOpen(true)} />
        </SidebarFooter>
        <SidebarRail aria-label={t("nav.toggleSidebar")} />
      </Sidebar>
      <SidebarInset>{children}</SidebarInset>
      <ProfileOverlay open={profileOpen} onOpenChange={setProfileOpen} />
    </SidebarProvider>
  );
}
```

(Only the `NavUser` call site, the new `profileOpen` state, and the new
`<ProfileOverlay>` line change — everything else in `AppShell`'s existing
JSX between `SidebarHeader` and `SidebarFooter` stays exactly as-is.)

Now that the "Konto" item is a plain `onClick` handler, not `asChild`
wrapping a `<Link>`, the now-unused `Link` import may still be needed
elsewhere in this file (it's also used for the `NAV_ITEMS` Chat/Suche
links and the "Konto"-adjacent... check: if `Link` has no other remaining
usage in this file after this change, remove the import; if `NAV_ITEMS`'
`<Link href={href}>` still uses it, as it does, keep it).

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- app-shell`
Expected: PASS, all tests including the new one.

- [ ] **Step 5: Run the full unit suite and the build**

Run: `cd frontend && npm test && npm run build`
Expected: both succeed.

- [ ] **Step 6: Commit**

```bash
cd frontend
git add src/components/app-shell.tsx tests/unit/app-shell.test.tsx
git commit -s -m "feat(frontend): open ProfileOverlay from the sidebar's Konto menu item"
```

---

### Task 4: Retire the standalone `/account` page

**Files:**
- Delete: `frontend/src/app/account/page.tsx`
- Delete: `frontend/src/app/account/account-page-content.tsx`
- Delete: `frontend/tests/unit/account-page.test.tsx`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new.

`AccountPageContent`'s three behaviors (login-required on no session,
login-required on fetch failure, renders the profile section once a
session is found) are already re-covered by `ProfileOverlay`'s own tests
(Task 2, Step 7) — this task only removes the now-duplicate page and its
test, no new coverage needed.

- [ ] **Step 1: Delete the page, its content component, and its test**

```bash
cd frontend
rm src/app/account/page.tsx src/app/account/account-page-content.tsx \
  tests/unit/account-page.test.tsx
rmdir src/app/account
```

- [ ] **Step 2: Confirm nothing else references the deleted files**

Run: `cd frontend && grep -rn "account-page-content\|app/account" src tests --include=*.tsx --include=*.ts`
Expected: no matches (the six section components under
`src/components/account/` are a different directory, `src/components/account/`,
not `src/app/account/` — they must NOT show up here; if they do, the grep
pattern matched something unintended, double-check).

- [ ] **Step 3: Run the full unit suite**

Run: `cd frontend && npm test`
Expected: PASS — the deleted `account-page.test.tsx` no longer runs (file
gone), everything else unaffected.

- [ ] **Step 4: Run the build**

Run: `cd frontend && npm run build`
Expected: succeeds — `/account` no longer appears in the route list, no
remaining import references the deleted files (a dangling import would be
a build-time module-resolution error, not a silent runtime issue).

- [ ] **Step 5: Note the Playwright e2e residual**

Any existing Playwright spec that navigates to `/account` (not run by this
plan's automated checks, same exclusion as Plans 1-3) will need updating
for the new overlay-based flow — flag this explicitly in the PR
description as a known follow-up, matching how the `/chats` retirement in
the previous plan handled the same situation.

- [ ] **Step 6: Commit**

```bash
cd frontend
git add -A src/app/account tests/unit/account-page.test.tsx
git commit -s -m "chore(frontend): retire the standalone /account page"
```

---

## After This Plan

Ask the user for explicit confirmation before pushing the branch and
before opening a PR (each triggers a billed STACKIT CI run — see Global
Constraints). Once confirmed: push `frontend/profile-overlay`, open a PR
against `main` on the `stackit` remote — mention the Playwright e2e
residual (Task 4, Step 5) in the PR description — wait for the CI
pipeline's `test-frontend` job to go green, then ask the user to merge
(same confirm-first rule applies). Plans 5 (Auth-Seiten) and 6 (Suche &
Dokument-Detail) remain in this redesign; neither depends on this plan.
