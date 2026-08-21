// frontend/tests/e2e/chat-and-history.spec.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { test, expect } from "@playwright/test";

test.describe("registration, login, and chat history", () => {
  test("a new user can register, and their session survives a page reload", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Anmelden" }).click();
    await page.getByRole("tab", { name: "Registrieren" }).click();

    const email = `e2e-${Date.now()}@example.de`;
    await page.getByLabel("E-Mail-Adresse").fill(email);
    await page.getByLabel("Passwort").fill("correct horse battery staple");
    await page.getByRole("button", { name: "Konto erstellen" }).click();

    // The dialog closes on success (AuthDialog's onSuccess handler).
    await expect(page.getByRole("dialog")).not.toBeVisible();

    await page.reload();
    const sessionResponse = await page.request.get("/api/auth/session");
    const sessionBody = await sessionResponse.json();
    expect(sessionBody.account?.email).toBe(email);
  });

  test("chat history is empty right after registration, then shows a session after chatting", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Anmelden" }).click();
    await page.getByRole("tab", { name: "Registrieren" }).click();
    const email = `e2e-history-${Date.now()}@example.de`;
    await page.getByLabel("E-Mail-Adresse").fill(email);
    await page.getByLabel("Passwort").fill("correct horse battery staple");
    await page.getByRole("button", { name: "Konto erstellen" }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible();

    await page.goto("/chats");
    await expect(page.getByText("Noch keine Chats vorhanden.")).toBeVisible();
  });
});
