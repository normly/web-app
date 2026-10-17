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
      if (url === "/api/chat/current") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url === "/api/chat/sessions") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 401 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({ session_id: null, answer: "Answer", answer_type: "fallback", paragraphs: ["Answer"], citations: [] }),
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
      if (url === "/api/chat/current") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url === "/api/chat/sessions") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 401 }));
      }
      if (url === "/api/chat/new-session") {
        // Resolve on a later tick, like a real request: the list is only
        // cleared once the server has answered.
        return new Promise((resolve) =>
          setTimeout(() => resolve(new Response(JSON.stringify({ ok: true }), { status: 200 })), 20),
        );
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({ session_id: null, answer: "Answer", answer_type: "fallback", paragraphs: ["Answer"], citations: [] }),
        ),
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
    await waitFor(() =>
      expect(screen.queryByText("Ist DIN EN ISO 9001 gültig?")).not.toBeInTheDocument(),
    );
  });

  it("restores the active session on load", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/chat/current") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              session_id: "sess-1",
              title: "Titel",
              messages: [
                { role: "user", content: "Alte Frage", paragraphs: ["Alte Frage"], citations: [] },
                {
                  role: "assistant",
                  content: "Alte Antwort",
                  paragraphs: ["Alte Antwort"],
                  citations: [
                    { document_id: "d1", segment_id: null, designation: "DGUV Vorschrift 1", section: null, paragraph_index: 0 },
                  ],
                },
              ],
            }),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    });

    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <HomePageContent />
        </JurisdictionProvider>
      </LocaleProvider>,
    );

    expect(await screen.findByText("Alte Frage")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "DGUV Vorschrift 1" })).toHaveAttribute("href", "/documents/d1");
  });

  it("opens a session from the sidebar", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/chat/current") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url === "/api/chat/sessions") {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              { id: "sess-9", session_token: "x", jurisdiction: "DE", language: "de", title: "Schutzbrillen", created_at: new Date().toISOString() },
            ]),
            { status: 200 },
          ),
        );
      }
      if (url === "/api/chat/sessions/sess-9/messages") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              session_id: "sess-9",
              title: "Schutzbrillen",
              messages: [{ role: "user", content: "Brauche ich eine Schutzbrille?", paragraphs: ["Brauche ich eine Schutzbrille?"], citations: [] }],
            }),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 404 }));
    });

    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <HomePageContent />
        </JurisdictionProvider>
      </LocaleProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Schutzbrillen" }));

    expect(await screen.findByText("Brauche ich eine Schutzbrille?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Schutzbrillen" })).toHaveAttribute("aria-current", "true");
  });

  it("asks for a title after the first answer of a new session and reloads the list", async () => {
    const calls: string[] = [];
    global.fetch = vi.fn().mockImplementation((url: string) => {
      calls.push(url);
      if (url === "/api/chat/current") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url === "/api/chat/sessions") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      if (url === "/api/chat/sessions/sess-new/title") {
        return Promise.resolve(new Response(JSON.stringify({ title: "Neu" }), { status: 200 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({ session_id: "sess-new", answer: "A", answer_type: "fallback", paragraphs: ["A"], citations: [] }),
          { status: 200 },
        ),
      );
    });

    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <HomePageContent />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByPlaceholderText("Frage stellen…"), { target: { value: "Frage" } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));

    await waitFor(() => expect(calls).toContain("/api/chat/sessions/sess-new/title"));
    // Initial load plus at least one reload after the answer. React may batch
    // the answer's and the title's refresh into one render, so the exact
    // count is not asserted.
    await waitFor(() =>
      expect(calls.filter((u) => u === "/api/chat/sessions").length).toBeGreaterThanOrEqual(2),
    );
  });
});
