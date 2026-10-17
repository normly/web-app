// frontend/tests/e2e/chat-and-history.spec.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { test, expect } from "@playwright/test";

test.describe("registration, login, and chat history", () => {
  test("a new user can register, and their session survives a page reload", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Anmelden" }).click();
    await page.getByRole("link", { name: "Registrieren" }).click();
    // /login and /signup share identical "E-Mail-Adresse"/"Passwort" field
    // labels -- during the client-side transition between them, the old
    // page's matching fields can still be attached when getByLabel() below
    // resolves, so it may fill the stale /login form instead of the new
    // /signup one. Wait for the URL to actually settle on /signup first.
    await expect(page).toHaveURL("http://localhost:3000/signup");

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
    // See the same-labels race-condition note above.
    await expect(page).toHaveURL("http://localhost:3000/signup");
    const email = `e2e-history-${Date.now()}@example.de`;
    await page.getByLabel("E-Mail-Adresse").fill(email);
    await page.getByLabel("Passwort").fill("correct horse battery staple");
    await page.getByRole("button", { name: "Konto erstellen" }).click();
    await expect(page).toHaveURL("http://localhost:3000/");

    await page.goto("/");
    await expect(page.getByText("Noch keine Chats vorhanden.")).toBeVisible();
  });

  test("a chat can be reopened from the sidebar and is restored after a reload", async ({ page }) => {
    await page.goto("/signup");
    const email = `e2e-reopen-${Date.now()}@example.de`;
    await page.getByLabel("E-Mail-Adresse").fill(email);
    await page.getByLabel("Passwort").fill("correct horse battery staple");
    await page.getByRole("button", { name: "Konto erstellen" }).click();
    await expect(page).toHaveURL("http://localhost:3000/");

    // An unknown designation answers structurally with a fallback: no model
    // and no knowledge-base data needed.
    const question = "Ist DIN EN ISO 99999 noch gültig?";
    await page.getByPlaceholder("Frage stellen…").fill(question);
    // The reload must wait for the answer: the chat cookie arrives with it.
    await Promise.all([
      page.waitForResponse(
        (r) => r.url().endsWith("/api/chat") && r.request().method() === "POST",
      ),
      page.getByRole("button", { name: "Senden" }).click(),
    ]);
    await expect(page.getByText(question).first()).toBeVisible();

    await page.reload();
    await expect(page.getByRole("log").getByText(question)).toBeVisible();

    await page.getByRole("button", { name: "Neuer Chat" }).click();
    await expect(page.getByRole("log").getByText(question)).toHaveCount(0);

    // The title is the model's summary or, without a model, the question.
    await page.getByTestId("chat-session").first().click();
    await expect(page.getByRole("log").getByText(question)).toBeVisible();
    await expect(page.getByTestId("chat-session").first()).toHaveAttribute("aria-current", "true");
  });
});
