// frontend/tests/e2e/search-and-browse.spec.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { test, expect } from "@playwright/test";

test.describe("search and document detail", () => {
  test("searching finds a seeded document and its detail page shows validity", async ({
    page,
  }) => {
    await page.goto("/search");
    await page.getByPlaceholder("Regelwerk suchen…").fill("Vorschrift");
    await page.getByRole("button", { name: "Suchen" }).click();

    await page.getByRole("link", { name: /DGUV Vorschrift/ }).click();
    await expect(page.getByText("Gültig")).toBeVisible();
  });

  test("the jurisdiction switcher is present and defaults to DE", async ({ page }) => {
    await page.goto("/search");
    await expect(page.getByLabel("Jurisdiktion")).toHaveValue("DE");
  });
});
