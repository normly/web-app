// frontend/tests/unit/magic-link-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { MagicLinkPageContent } from "@/app/magic-link/magic-link-page-content";

const originalFetch = global.fetch;

describe("MagicLinkPageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders the heading, description, and a link back to login", () => {
    render(
      <LocaleProvider initialLocale="de">
        <MagicLinkPageContent />
      </LocaleProvider>,
    );
    expect(screen.getByRole("heading", { name: "Mit Link anmelden" })).toBeInTheDocument();
    expect(
      screen.getByText("Gib deine E-Mail-Adresse ein, wir schicken dir einen Anmeldelink."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zurück zur Anmeldung" })).toHaveAttribute(
      "href", "/login",
    );
  });

  it("shows the confirmation message after requesting a link", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    render(
      <LocaleProvider initialLocale="de">
        <MagicLinkPageContent />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), {
      target: { value: "a@example.de" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Anmeldelink senden" }));
    await waitFor(() => expect(screen.getByText("Anmeldelink senden ✓")).toBeInTheDocument());
  });
});
