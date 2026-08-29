// frontend/tests/unit/app-header.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { JurisdictionProvider } from "@/lib/jurisdiction/provider";
import { AppHeader } from "@/components/app-header";

const originalFetch = global.fetch;

describe("AppHeader", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders the instance name when no logo is configured", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <AppHeader instanceName="Beispiel-Institut" logoPath={null} />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    expect(screen.getByText("Beispiel-Institut")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith("/api/auth/session"));
  });

  it("renders a logo image instead of the plain name when logoPath is set", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <AppHeader instanceName="Beispiel-Institut" logoPath="/logo.svg" />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    const logo = await screen.findByRole("img");
    expect(logo).toHaveAttribute("src", "/logo.svg");
    expect(logo).toHaveAttribute("alt", "Beispiel-Institut");
  });

  it("shows the login trigger when the session check returns no account", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <AppHeader instanceName="normly" logoPath={null} />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Anmelden" })).toBeInTheDocument(),
    );
  });

  it("shows the account email and a logout button when the session check returns an account", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ account: { accountId: "1", email: "a@example.de" } }),
      ),
    );
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <AppHeader instanceName="normly" logoPath={null} />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    await waitFor(() => expect(screen.getByText("a@example.de")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Abmelden" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Anmelden" })).not.toBeInTheDocument();
  });

  it("omits the history link when showHistoryLink is false", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <AppHeader instanceName="normly" logoPath={null} showHistoryLink={false} />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    expect(screen.queryByRole("link", { name: "Verlauf" })).not.toBeInTheDocument();
  });
  it("always links to the search page, independent of showHistoryLink", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <AppHeader instanceName="normly" logoPath={null} showHistoryLink={false} />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    expect(screen.getByRole("link", { name: "Suche" })).toHaveAttribute("href", "/search");
  });
});
