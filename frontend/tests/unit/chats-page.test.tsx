// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ChatsPageContent } from "@/app/chats/chats-page-content";

const originalFetch = global.fetch;

describe("ChatsPageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the login-required message when there is no account session", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 401 }));
    render(
      <LocaleProvider initialLocale="de">
        <ChatsPageContent />
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(
        screen.getByText("Melde dich an, um deinen Chat-Verlauf zu sehen."),
      ).toBeInTheDocument(),
    );
  });

  it("shows an empty-state message when the account has no sessions yet", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    render(
      <LocaleProvider initialLocale="de">
        <ChatsPageContent />
      </LocaleProvider>,
    );
    await waitFor(() => expect(screen.getByText("Noch keine Chats vorhanden.")).toBeInTheDocument());
  });

  it("lists sessions as plain text, without a reopen link or the raw session token", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "1", session_token: "tok-1", jurisdiction: "DE", language: "de",
            created_at: "2026-01-01T00:00:00Z",
          },
        ]),
        { status: 200 },
      ),
    );
    render(
      <LocaleProvider initialLocale="de">
        <ChatsPageContent />
      </LocaleProvider>,
    );
    // Full click-to-reopen resumption isn't built yet (`/` never reads a
    // `session` query param), so the entry must not be an <a>/<Link> --
    // and, since that link used to be `/?session=<token>`, the raw session
    // token credential must never appear anywhere in the rendered output.
    await waitFor(() =>
      expect(screen.getByText(new Date("2026-01-01T00:00:00Z").toLocaleDateString())).toBeInTheDocument(),
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(document.body.textContent).not.toContain("tok-1");
    expect(document.body.innerHTML).not.toContain("tok-1");
  });
});
