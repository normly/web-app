// frontend/playwright.config.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  webServer: {
    command: "npm run build && npm run start",
    url: "http://localhost:3000",
    reuseExistingServer: false,
    timeout: 120_000,
  },
  // Chromium's "Chrome for Testing" build Playwright downloads ships only
  // the en-US locale resources and always reports Accept-Language: en-US
  // regardless of the host OS locale (LANG/LC_ALL have no effect on it).
  // The app's own locale detection (frontend/src/app/layout.tsx) is
  // correct and per-spec: German unless the browser's Accept-Language
  // explicitly starts with "en". Pinning the test browser's locale to
  // de-DE makes the suite exercise the product's real default -- what a
  // German-market user's browser actually sends -- instead of an
  // English-only test-runner artifact that the app was never meant to
  // special-case.
  use: { baseURL: "http://localhost:3000", locale: "de-DE" },
});
