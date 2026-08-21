// frontend/vitest.config.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/unit/setup.ts"],
    // Scope discovery to the unit suite only. Without this, Vitest's
    // default glob also picks up tests/e2e/*.spec.ts (added in Task 12),
    // which use the Playwright Test runner's own test()/describe() API
    // and fail immediately under Vitest ("did not expect test() to be
    // called here").
    include: ["tests/unit/**/*.{test,spec}.{ts,tsx}"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
