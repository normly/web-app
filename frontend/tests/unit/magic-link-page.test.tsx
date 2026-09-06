// frontend/tests/unit/magic-link-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { MagicLinkPageContent } from "@/app/magic-link/magic-link-page-content";

const push = vi.fn();
const searchParams = vi.fn(() => new URLSearchParams());
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => searchParams(),
}));

const originalFetch = global.fetch;

describe("MagicLinkPageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    push.mockClear();
    searchParams.mockReset();
    searchParams.mockReturnValue(new URLSearchParams());
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

  it("confirms the token from the URL and navigates home on success", async () => {
    searchParams.mockReturnValue(new URLSearchParams("token=valid-token"));
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    render(
      <LocaleProvider initialLocale="de">
        <MagicLinkPageContent />
      </LocaleProvider>,
    );
    expect(screen.getByText("Du wirst angemeldet…")).toBeInTheDocument();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/auth/magic-link/confirm");
    expect(JSON.parse(init.body)).toEqual({ token: "valid-token" });
  });

  it("shows the invalid-link message when the token is rejected", async () => {
    searchParams.mockReturnValue(new URLSearchParams("token=bad-token"));
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 400 }));
    render(
      <LocaleProvider initialLocale="de">
        <MagicLinkPageContent />
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByText("Dieser Link ist ungültig oder abgelaufen.")).toBeInTheDocument(),
    );
    expect(push).not.toHaveBeenCalled();
  });
});
