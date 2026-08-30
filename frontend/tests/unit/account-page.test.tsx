// frontend/tests/unit/account-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { AccountPageContent } from "@/app/account/account-page-content";

const originalFetch = global.fetch;

describe("AccountPageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the login-required message when there is no session", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ account: null }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <AccountPageContent />
      </LocaleProvider>,
    );

    await waitFor(() =>
      expect(screen.getByText("Melde dich an, um dein Konto zu verwalten.")).toBeInTheDocument(),
    );
  });

  it("shows the login-required message when the session fetch rejects", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("network error"));

    render(
      <LocaleProvider initialLocale="de">
        <AccountPageContent />
      </LocaleProvider>,
    );

    await waitFor(() =>
      expect(screen.getByText("Melde dich an, um dein Konto zu verwalten.")).toBeInTheDocument(),
    );
  });

  it("renders the name/avatar section once a session is found", async () => {
    global.fetch = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/account/sessions")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            account: {
              accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
              avatarDataUrl: null,
            },
          }),
          { status: 200 },
        ),
      );
    });

    render(
      <LocaleProvider initialLocale="de">
        <AccountPageContent />
      </LocaleProvider>,
    );

    await waitFor(() =>
      expect(screen.getByText("Name und Profilbild")).toBeInTheDocument(),
    );
  });
});
