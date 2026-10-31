// frontend/tests/e2e/user-management.spec.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { expect, test } from "@playwright/test";

// Needs: a running stack, an administrator created with
// `docker compose run --rm pipeline grant-admin --email $E2E_ADMIN_EMAIL`
// and Mailpit's API (compose service `mailpit`, default http://127.0.0.1:8025).
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL;
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD;
const MAILPIT = process.env.E2E_MAILPIT_URL ?? "http://127.0.0.1:8025";

test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD");

async function invitationLink(request: import("@playwright/test").APIRequestContext, to: string) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const list = await (await request.get(`${MAILPIT}/api/v1/search?query=to:${encodeURIComponent(to)}`)).json();
    if (list.messages?.length) {
      const message = await (await request.get(`${MAILPIT}/api/v1/message/${list.messages[0].ID}`)).json();
      const match = /https?:\/\/\S+\/invitation\?token=[\w-]+/.exec(message.Text);
      if (match) return match[0];
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`no invitation mail for ${to}`);
}

test("an administrator invites a publisher, who accepts; then blocks them", async ({ page, browser, request }) => {
  const invited = `e2e-publisher-${Date.now()}@example.de`;
  const publisher = `E2E Verlag ${Date.now()}`;

  await page.goto("/login");
  await page.getByLabel("E-Mail-Adresse").fill(ADMIN_EMAIL!);
  await page.getByLabel("Passwort").fill(ADMIN_PASSWORD!);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await page.getByRole("link", { name: "Nutzermanagement" }).click();
  await expect(page).toHaveURL(/\/admin\/users/);

  await page.getByRole("button", { name: "Nutzer einladen" }).click();
  await page.getByLabel("E-Mail-Adresse").fill(invited);
  await page.getByLabel("Rolle").selectOption("publisher");
  await page.getByLabel("Verlagszuordnung").selectOption("__new__");
  await page.getByLabel("Name des Verlags").fill(publisher);
  await page.getByRole("button", { name: "Anlegen" }).click();
  await page.getByRole("button", { name: "Einladung senden" }).click();
  await expect(page.getByRole("status")).toContainText(invited);

  const link = await invitationLink(request, invited);
  const invitee = await (await browser.newContext({ locale: "de-DE" })).newPage();
  await invitee.goto(link.replace(/^https?:\/\/[^/]+/, ""));
  await invitee.getByRole("button", { name: "Einladung annehmen" }).click();
  await expect(invitee).toHaveURL(/\/$/);

  await page.getByRole("searchbox", { name: "Konten durchsuchen" }).fill(invited);
  const row = page.getByRole("row", { name: new RegExp(invited) });
  await expect(row).toContainText(publisher);
  await expect(row).toContainText("Aktiv");

  await row.getByRole("button", { name: `Aktionen für ${invited}` }).click();
  await page.getByRole("menuitem", { name: "Sperren" }).click();
  await page.getByRole("button", { name: "Sperren" }).click();
  await expect(row).toContainText("Gesperrt");

  // The menu-to-dialog hand-off must not leave the page inert (Radix
  // pointer-events: none on body): a later click still works.
  await page.getByRole("searchbox", { name: "Konten durchsuchen" }).click();
  await expect(page.getByRole("searchbox", { name: "Konten durchsuchen" })).toBeFocused();
  await row.getByRole("button", { name: `Aktionen für ${invited}` }).click();
  await expect(page.getByRole("menuitem").first()).toBeVisible();
  await page.keyboard.press("Escape");

  await invitee.reload();
  await expect(invitee.getByRole("link", { name: "Anmelden" })).toBeVisible();
});
