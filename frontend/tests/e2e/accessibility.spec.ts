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

test("the login dialog is keyboard-operable", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Anmelden" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
});
