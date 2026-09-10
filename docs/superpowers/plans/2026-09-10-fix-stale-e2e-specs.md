# Fix Stale E2E Specs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 Playwright e2e spec files that have been broken since 2026-09-06, when the header's "Anmelden" login control changed from a `<button>` (opening a modal) to a `<Link>` navigating to a full `/login` page — the e2e specs were never updated to match.

**Architecture:** A single task. All 3 files share the exact same root cause (a button→link role change plus the disappearance of a login/registration dialog in favor of real page navigation) and the exact same fix pattern, and verifying the fix requires standing up the same real backend-services + seeded-database environment for all of them — splitting into multiple tasks would mean repeating that setup for no benefit.

**Tech Stack:** Playwright, TypeScript — `frontend/tests/e2e/`.

## Global Constraints

- DCO `Signed-off-by` (via `git commit -s` — the human's identity is already configured in git, never a literal placeholder line) + Conventional Commits + a separate `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer on every commit.
- Test files only — no production source code changes. This is a stale-test bug, not a product bug.
- `frontend/tests/e2e/search-and-browse.spec.ts` and the first test in `frontend/tests/e2e/accessibility.spec.ts` (the WCAG scan of `/`) are already passing and out of scope — do not modify them, and the final full-suite run must prove they still pass.
- `account-management.spec.ts`'s `openProfileOverlay()` helper and its `getByRole("dialog")` assertions are correct and unrelated (a different, still-real dialog — the account-management overlay, not the login flow) — do not touch them.
- `account-management.spec.ts`'s avatar-upload, session-list, and export-download tests are unaffected by this bug — preserve them byte-for-byte except for the one shared helper they all call.

---

### Task 1: Fix the 3 stale e2e spec files

**Files:**
- Modify: `frontend/tests/e2e/account-management.spec.ts`
- Modify: `frontend/tests/e2e/chat-and-history.spec.ts`
- Modify: `frontend/tests/e2e/accessibility.spec.ts`

**Interfaces:**
- Consumes: nothing from another task — this plan has only one task.
- Produces: nothing another task depends on.

**Context — read this before touching anything:**

Commit `53ce3ed3` (2026-09-06) changed the login trigger in `frontend/src/components/app-shell.tsx` (the `NavUser` component's logged-out branch, which is what actually renders on `/` and `/search` — the two routes these specs visit) from a `<button>` opening an `AuthDialog` modal to:
```tsx
<Button variant="outline" asChild>
  <Link href="/login">{t("auth.loginTab")}</Link>
</Button>
```
`asChild` makes Radix swap in the `Link`'s own `<a>` element, so this control's accessible role is now **`link`**, not `button`. Its text is unchanged: `t("auth.loginTab")` resolves to **"Anmelden"**.

There is no dialog anywhere in the login/registration flow anymore (verified this session via `grep -rn "role=\"dialog\"\|<Dialog>" frontend/src/app/login frontend/src/app/signup frontend/src/components/auth` — zero hits). `/login` (`frontend/src/app/login/login-page-content.tsx`) is a full page containing `LoginForm` — labels "E-Mail-Adresse"/"Passwort" unchanged, submit button text **"Anmelden"** (yes, the same text as the link that got you here — but it's the only element with role `button` named "Anmelden" once you're actually on `/login`, so `getByRole("button", { name: "Anmelden" })` is unambiguous there) — plus a "Noch kein Konto?" paragraph containing a plain `<Link href="/signup">Registrieren</Link>` (a real page navigation, NOT a tab). `/signup` (`frontend/src/app/signup/signup-page-content.tsx`) is a separate full page containing `RegisterForm` — same labels, submit button text **"Konto erstellen"** (unchanged from before). Both `LoginForm` and `RegisterForm` call `onSuccess={() => router.push("/")}` on success — a client-side navigation to `/`, never a dialog closing.

The one dialog that IS still real and must not be touched: the account-management "Konto" overlay (`frontend/src/components/account/profile-overlay.tsx`), used by `account-management.spec.ts`'s existing `openProfileOverlay()` helper.

`frontend/playwright.config.ts` pins `baseURL: "http://localhost:3000"` and `locale: "de-DE"` — every German string used below is exactly what a real browser session renders.

- [ ] **Step 1: Replace `frontend/tests/e2e/account-management.spec.ts` with this exact content**

```ts
// frontend/tests/e2e/account-management.spec.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { test, expect } from "@playwright/test";

async function openProfileOverlay(page: import("@playwright/test").Page) {
  // The trigger button's accessible name includes the Avatar fallback's
  // initials text node alongside the email (same issue Task 3's unit test
  // hit, see app-shell.test.tsx) -- match on the email substring via
  // regex, not an exact name.
  await page.getByRole("button", { name: /.+@.+/ }).click();
  await page.getByRole("menuitem", { name: "Konto" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
}

async function registerAndOpenAccountPage(page: import("@playwright/test").Page) {
  const email = `e2e-account-${Date.now()}@example.de`;
  await page.goto("/");
  await page.getByRole("link", { name: "Anmelden" }).click();
  await page.getByRole("link", { name: "Registrieren" }).click();
  await page.getByLabel("E-Mail-Adresse").fill(email);
  await page.getByLabel("Passwort").fill("correct horse battery staple");
  await page.getByRole("button", { name: "Konto erstellen" }).click();
  // RegisterForm's onSuccess navigates to "/" (no dialog to close anymore --
  // /login and /signup are full pages, not a modal).
  await expect(page).toHaveURL("http://localhost:3000/");

  await openProfileOverlay(page);
  return email;
}

test.describe("account management", () => {
  test("a user can set their name and it persists across a reload", async ({ page }) => {
    await registerAndOpenAccountPage(page);

    await page.getByLabel("Vorname").fill("Jamie");
    await page.getByLabel("Nachname").fill("Weber");
    await page.getByRole("button", { name: "Speichern" }).click();

    await page.reload();
    await openProfileOverlay(page);
    await expect(page.getByLabel("Vorname")).toHaveValue("Jamie");
  });

  test("a user can upload and then remove an avatar", async ({ page }) => {
    await registerAndOpenAccountPage(page);
    const png1x1 = Buffer.from(
      "89504e470d0a1a0a0000000d49484452000000010000000108020000009077" +
        "53de0000000c49444154789c63f8cfc0000003010100c9fe92ef0000000049454e44ae426082",
      "hex",
    );
    await page.getByLabel("Bild hochladen").setInputFiles({
      name: "avatar.png", mimeType: "image/png", buffer: png1x1,
    });
    await expect(page.getByRole("img", { name: "Profilbild" }).first()).toBeVisible();

    await page.getByRole("button", { name: "Bild entfernen" }).click();
    await expect(page.getByRole("button", { name: "Bild entfernen" })).not.toBeVisible();
  });

  test("a user can change their password and log in with the new one", async ({ page }) => {
    const email = await registerAndOpenAccountPage(page);
    await page.getByRole("button", { name: "Passwort" }).click();

    await page.getByLabel("Aktuelles Passwort").fill("correct horse battery staple");
    await page.getByLabel("Neues Passwort").fill("a brand new secret");
    await page.getByRole("button", { name: "Passwort ändern" }).click();
    await expect(page.getByText("Dein Passwort wurde geändert.")).toBeVisible();

    await page.request.post("/api/auth/logout");
    await page.goto("/");
    await page.getByRole("link", { name: "Anmelden" }).click();
    await page.getByLabel("E-Mail-Adresse").fill(email);
    await page.getByLabel("Passwort").fill("a brand new secret");
    await page.getByRole("button", { name: "Anmelden" }).click();
    await expect(page).toHaveURL("http://localhost:3000/");
  });

  test("the current session is listed and cannot be revoked from itself", async ({ page }) => {
    await registerAndOpenAccountPage(page);
    await page.getByRole("button", { name: "Aktive Sitzungen" }).click();

    await expect(page.getByText("Dieses Gerät")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sitzung beenden" })).not.toBeVisible();
  });

  test("a user can download their data export", async ({ page }) => {
    await registerAndOpenAccountPage(page);
    await page.getByRole("button", { name: "Konto & Daten" }).click();

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Export herunterladen" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("normly-konto-export.json");
  });

  test("deleting the account requires the confirmation email and ends the session", async ({
    page,
  }) => {
    const email = await registerAndOpenAccountPage(page);
    await page.getByRole("button", { name: "Konto & Daten" }).click();

    const deleteButton = page.getByRole("button", { name: "Konto endgültig löschen" });
    await expect(deleteButton).toBeDisabled();

    await page.getByLabel("Gib zur Bestätigung deine E-Mail-Adresse ein").fill(email);
    await page.getByLabel("Passwort zur Bestätigung").fill("correct horse battery staple");
    await deleteButton.click();

    await expect(page.getByRole("link", { name: "Anmelden" })).toBeVisible();
  });
});
```

- [ ] **Step 2: Replace `frontend/tests/e2e/chat-and-history.spec.ts` with this exact content**

```ts
// frontend/tests/e2e/chat-and-history.spec.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { test, expect } from "@playwright/test";

test.describe("registration, login, and chat history", () => {
  test("a new user can register, and their session survives a page reload", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Anmelden" }).click();
    await page.getByRole("link", { name: "Registrieren" }).click();

    const email = `e2e-${Date.now()}@example.de`;
    await page.getByLabel("E-Mail-Adresse").fill(email);
    await page.getByLabel("Passwort").fill("correct horse battery staple");
    await page.getByRole("button", { name: "Konto erstellen" }).click();

    // RegisterForm's onSuccess navigates to "/" (no dialog to close anymore --
    // /login and /signup are full pages, not a modal).
    await expect(page).toHaveURL("http://localhost:3000/");

    await page.reload();
    const sessionResponse = await page.request.get("/api/auth/session");
    const sessionBody = await sessionResponse.json();
    expect(sessionBody.account?.email).toBe(email);
  });

  test("chat history is empty right after registration, then shows a session after chatting", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Anmelden" }).click();
    await page.getByRole("link", { name: "Registrieren" }).click();
    const email = `e2e-history-${Date.now()}@example.de`;
    await page.getByLabel("E-Mail-Adresse").fill(email);
    await page.getByLabel("Passwort").fill("correct horse battery staple");
    await page.getByRole("button", { name: "Konto erstellen" }).click();
    await expect(page).toHaveURL("http://localhost:3000/");

    await page.goto("/");
    await expect(page.getByText("Noch keine Chats vorhanden.")).toBeVisible();
  });
});
```

- [ ] **Step 3: Replace `frontend/tests/e2e/accessibility.spec.ts` with this exact content**

The first test (WCAG scan of `/`) is unaffected by this bug and stays exactly as it is. The second test targeted a dialog that no longer exists — it's rewritten to verify what the current UI actually offers: that the "Anmelden" link (the login flow's entry point) is keyboard-reachable. Testing an Escape-key close is deliberately NOT reintroduced — there is nothing to dismiss now that this is a page navigation, not an overlay.

```ts
// frontend/tests/e2e/accessibility.spec.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("the chat page has no automatically detectable WCAG 2.1 AA violations", async ({ page }) => {
  await page.goto("/");
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations).toEqual([]);
});

test("the Anmelden link is keyboard-operable", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Anmelden" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL("http://localhost:3000/login");
});
```

- [ ] **Step 4: Set up the real backend environment**

This needs real running services and a seeded database — the same setup already used earlier this session for the Next.js-upgrade plan's own e2e gate. In your own worktree (this environment does not persist across worktrees):

1. Start Postgres: `docker start normly-pg` (or, if that container doesn't exist in your environment, create an equivalent one — user `normly`, password `normly`, database `normly`, port `5432`).
2. Migrate to head — from `core/`, using any venv that has `normly-core` installed editable (e.g. `accounts/.venv`):
```bash
accounts/.venv/bin/python -c "
from alembic.config import Config
from alembic import command
cfg = Config('alembic.ini')
cfg.set_main_option('sqlalchemy.url', 'postgresql+psycopg://normly:normly@localhost:5432/normly')
command.upgrade(cfg, 'head')
"
```
(run from inside `core/`, so `alembic.ini` resolves).
3. Seed one real document (needed for `search-and-browse.spec.ts` to keep passing):
```bash
mkdir -p /tmp/dguv-seed
cp core/tests/fixtures/dguv_sample_vorschrift.pdf /tmp/dguv-seed/
NORMLY_DATABASE_URL="postgresql+psycopg://normly:normly@localhost:5432/normly" \
  accounts/.venv/bin/python -m normly_core.pipeline.cli ingest --directory /tmp/dguv-seed dguv
```
4. Start the three backend services (each needs its own venv set up per this repo's established pattern — `python3.12 -m venv --without-pip .venv`, bootstrap pip from an already-working venv, `pip install -e ../core -e ".[dev]"`):
```bash
# accounts, port 8001
cd accounts && NORMLY_DATABASE_URL="postgresql+psycopg://normly:normly@localhost:5432/normly" \
  .venv/bin/uvicorn normly_accounts.main:app --host 0.0.0.0 --port 8001 &

# api, port 8002
cd api && NORMLY_DATABASE_URL="postgresql+psycopg://normly:normly@localhost:5432/normly" \
  .venv/bin/uvicorn normly_api.main:app --host 0.0.0.0 --port 8002 &

# chat, port 8003 -- needs NORMLY_OLLAMA_BASE_URL/NORMLY_OLLAMA_MODEL SET (not
# necessarily reachable -- only the lifespan() client construction needs
# these env vars present; no e2e spec triggers a real chat completion)
cd chat && NORMLY_DATABASE_URL="postgresql+psycopg://normly:normly@localhost:5432/normly" \
  NORMLY_ACCOUNTS_BASE_URL="http://localhost:8001" NORMLY_API_BASE_URL="http://localhost:8002" \
  NORMLY_OLLAMA_BASE_URL="http://localhost:11434" NORMLY_OLLAMA_MODEL="llama3" \
  .venv/bin/uvicorn normly_chat.main:app --host 0.0.0.0 --port 8003 &
```
5. Verify all three respond: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:800{1,2,3}/openapi.json` — expect `200` three times.

- [ ] **Step 5: Run the full Playwright suite**

Export the frontend env vars the BFF routes need, then run all 4 spec files (not just the 3 you fixed):

```bash
cd frontend
export NORMLY_API_BASE_URL="http://localhost:8002"
export NORMLY_ACCOUNTS_BASE_URL="http://localhost:8001"
export NORMLY_CHAT_BASE_URL="http://localhost:8003"
npx playwright test
```

Expected: all 12 tests pass across all 4 spec files (the 2 pre-existing passes in `search-and-browse.spec.ts`, the 1 pre-existing pass plus your 1 fixed test in `accessibility.spec.ts`, and all tests in the 2 files you rewrote). If anything fails, read Playwright's own `test-results/*/error-context.md` output for the actual DOM snapshot at failure time rather than guessing — the grounding in this task's Context section was verified directly against the real current source, but re-confirm against what the real running app actually renders if a selector doesn't match.

- [ ] **Step 6: Stop the backend services**

```bash
pkill -f "uvicorn normly_accounts"
pkill -f "uvicorn normly_api"
pkill -f "uvicorn normly_chat"
docker stop normly-pg
```

- [ ] **Step 7: Commit**

```bash
git add frontend/tests/e2e/account-management.spec.ts frontend/tests/e2e/chat-and-history.spec.ts frontend/tests/e2e/accessibility.spec.ts
git commit -s -m "fix(frontend): update e2e specs for the /login page navigation flow

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
(Use `git commit -s` alone — do not type a literal `Signed-off-by` line yourself, `-s` adds the real one from git config.)
