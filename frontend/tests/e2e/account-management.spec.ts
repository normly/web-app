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
  await page.getByRole("button", { name: "Anmelden" }).click();
  await page.getByRole("tab", { name: "Registrieren" }).click();
  await page.getByLabel("E-Mail-Adresse").fill(email);
  await page.getByLabel("Passwort").fill("correct horse battery staple");
  await page.getByRole("button", { name: "Konto erstellen" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();

  await openProfileOverlay(page);
  return email;
}

test.describe("account management", () => {
  test("a user can set their name and it persists across a reload", async ({ page }) => {
    // AppHeader only ever displays the account's email next to the avatar
    // (Task 10) -- first/last name are surfaced nowhere but this form
    // itself, so persistence-after-reload is the correct thing to assert
    // here, not visible text elsewhere on the page.
    await registerAndOpenAccountPage(page);

    await page.getByLabel("Vorname").fill("Jamie");
    await page.getByLabel("Nachname").fill("Weber");
    await page.getByRole("button", { name: "Speichern" }).click();

    await page.reload();
    // The overlay is client-only React state, not persisted across a
    // reload -- the dialog is closed after reload even though the
    // session cookie (and therefore the account itself) survives it.
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

    // The file input is a descendant of a <label>Bild hochladen<input .../></label>
    // -- Playwright's getByLabel() resolves this to the <input> itself
    // (wrapping counts as association, same as a for=/id= pair), which is
    // the element setInputFiles() requires; getByText() would instead
    // return the label and fail with "not an HTMLInputElement".
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

    // registerAndOpenAccountPage() registers with a password, so the
    // account already has a password_hash -- password.py's set_password
    // requires and verifies the current password whenever one is set
    // (see accounts/tests/test_set_password.py), so it must be filled in
    // here too, not just the new password.
    await page.getByLabel("Aktuelles Passwort").fill("correct horse battery staple");
    await page.getByLabel("Neues Passwort").fill("a brand new secret");
    await page.getByRole("button", { name: "Passwort ändern" }).click();
    await expect(page.getByText("Dein Passwort wurde geändert.")).toBeVisible();

    await page.request.post("/api/auth/logout");
    await page.goto("/");
    await page.getByRole("button", { name: "Anmelden" }).click();
    await page.getByLabel("E-Mail-Adresse").fill(email);
    await page.getByLabel("Passwort").fill("a brand new secret");
    await page.getByRole("button", { name: "Anmelden" }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible();
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

    // DeleteAccountSection reloads the page on success (Task 14) -- the
    // reload re-fetches /api/auth/session, which now finds the cookie
    // cleared. AppShell's NavUser falls back to the login trigger, and the
    // overlay itself is gone (client-only state, reset by the reload), so
    // assert on the logged-out sidebar state rather than the overlay text.
    await expect(page.getByRole("button", { name: "Anmelden" })).toBeVisible();
  });
});
