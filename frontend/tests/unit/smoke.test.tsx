// frontend/tests/unit/smoke.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import HomePage from "@/app/page";

const originalFetch = global.fetch;

describe("HomePage", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders without crashing", () => {
    // AppHeader checks /api/auth/session on mount.
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <HomePage />
      </LocaleProvider>,
    );
    expect(screen.getByPlaceholderText("Frage stellen…")).toBeInTheDocument();
  });

  it("renders a link to the chat history page", () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <HomePage />
      </LocaleProvider>,
    );
    const historyLink = screen.getByRole("link", { name: "Verlauf" });
    expect(historyLink).toBeInTheDocument();
    expect(historyLink).toHaveAttribute("href", "/chats");
  });
});
