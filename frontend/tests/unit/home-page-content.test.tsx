// frontend/tests/unit/home-page-content.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { JurisdictionProvider } from "@/lib/jurisdiction/provider";
import { HomePageContent } from "@/app/home-page-content";

const originalFetch = global.fetch;

describe("HomePageContent", () => {
  beforeEach(() => {
    // jsdom has no matchMedia -- ChatShell's SidebarProvider (via the
    // sidebar primitive's internal useIsMobile() hook) calls it on every
    // render, same precedent as app-shell.test.tsx/page-header.test.tsx.
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("sends the current UI locale as the chat language, not a hardcoded 'de'", async () => {
    // ChatShell now mounts ChatHistorySidebar alongside the chat panel,
    // which fires its own fetch("/api/chat/sessions") on mount -- the mock
    // must tell that call apart from the /api/chat POST this test actually
    // exercises, both so each gets a fresh Response body (a single shared
    // Response can only have .json() read once) and so the assertion below
    // finds the right call instead of assuming it's mock.calls[0].
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/chat/sessions") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 401 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({ answer: "Answer", answer_type: "fallback", citations: [] }),
          { status: 200 },
        ),
      );
    });
    render(
      <LocaleProvider initialLocale="en">
        <JurisdictionProvider initialJurisdiction="DE">
          <HomePageContent />
        </JurisdictionProvider>
      </LocaleProvider>,
    );

    fireEvent.change(screen.getByPlaceholderText("Ask a question…"), {
      target: { value: "Is DIN EN ISO 9001 valid?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith("/api/chat", expect.anything()));
    const chatCall = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      ([url]) => url === "/api/chat",
    );
    const [, init] = chatCall!;
    const body = JSON.parse(init.body as string);
    expect(body.language).toBe("en");
  });

  it("clears the message list and calls the new-session endpoint when Neuer Chat is clicked", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/chat/sessions") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 401 }));
      }
      if (url === "/api/chat/new-session") {
        return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
      }
      return Promise.resolve(
        new Response(JSON.stringify({ answer: "Answer", answer_type: "fallback", citations: [] })),
      );
    });
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;

    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <HomePageContent />
        </JurisdictionProvider>
      </LocaleProvider>,
    );

    fireEvent.change(screen.getByPlaceholderText("Frage stellen…"), {
      target: { value: "Ist DIN EN ISO 9001 gültig?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    await waitFor(() => expect(screen.getByText("Ist DIN EN ISO 9001 gültig?")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Neuer Chat" }));
    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith("/api/chat/new-session", { method: "POST" }),
    );
    expect(screen.queryByText("Ist DIN EN ISO 9001 gültig?")).not.toBeInTheDocument();
  });
});
