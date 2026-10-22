// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { test, expect } from "@playwright/test";

test.describe("AI answer limits", () => {
  test("a spent quota shows the sign-in notice in the chat", async ({ page }) => {
    // The limit itself is covered by chat/'s tests; this checks the UI path
    // from a 429 to the notice without spending real quota.
    await page.route("**/api/chat", (route) =>
      route.fulfill({
        status: 429,
        contentType: "application/json",
        body: JSON.stringify({
          detail: { reason: "quota_exhausted", resets_at: "2099-01-01T00:00:00Z", anonymous: true },
        }),
      }),
    );
    await page.goto("/");
    await page.getByPlaceholder("Frage stellen…").fill("Welche Schutzausrüstung ist beim Schweißen vorgeschrieben?");
    await page.getByRole("button", { name: "Senden" }).click();

    await expect(page.getByText(/Melde dich an, um mehr zu erhalten/)).toBeVisible();
  });

  test("a signed-in user sees their AI answers in the profile", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Anmelden" }).click();
    await page.getByRole("link", { name: "Registrieren" }).click();
    // See the same-labels race-condition note in chat-and-history.spec.ts.
    await expect(page).toHaveURL("http://localhost:3000/signup");
    await page.getByLabel("E-Mail-Adresse").fill(`e2e-usage-${Date.now()}@example.de`);
    await page.getByLabel("Passwort").fill("correct horse battery staple");
    await page.getByRole("button", { name: "Konto erstellen" }).click();
    await expect(page).toHaveURL("http://localhost:3000/");

    // Open the profile the same way account-management.spec.ts does.
    await page.getByRole("button", { name: /.+@.+/ }).click();
    await page.getByRole("menuitem", { name: "Konto" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByRole("button", { name: "Nutzung" }).click();

    await expect(page.getByText(/KI-Antworten heute: 0 von \d+/)).toBeVisible();
  });
});
