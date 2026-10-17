// frontend/tests/unit/home-page-content.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { JurisdictionProvider, useJurisdiction } from "@/lib/jurisdiction/provider";
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
              { id: "sess-9", jurisdiction: "DE", language: "de", title: "Schutzbrillen", created_at: new Date().toISOString() },
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

  const sessionList = [
    { id: "sess-9", jurisdiction: "DE", language: "de", title: "Schutzbrillen", created_at: new Date().toISOString() },
  ];
  const sessionMessages = {
    session_id: "sess-9",
    title: "Schutzbrillen",
    messages: [{ role: "user", content: "Brauche ich eine Schutzbrille?", paragraphs: ["Brauche ich eine Schutzbrille?"], citations: [] }],
  };
  const renderHome = () =>
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <HomePageContent />
        </JurisdictionProvider>
      </LocaleProvider>,
    );

  it("resets the view and calls new-session when the active session is deleted", async () => {
    const calls: string[] = [];
    global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url === "/api/chat/current") return Promise.resolve(new Response(null, { status: 204 }));
      if (url === "/api/chat/sessions" && !init?.method) {
        return Promise.resolve(new Response(JSON.stringify(sessionList), { status: 200 }));
      }
      if (url === "/api/chat/sessions/sess-9/messages") {
        return Promise.resolve(new Response(JSON.stringify(sessionMessages), { status: 200 }));
      }
      if (init?.method === "DELETE") return Promise.resolve(new Response(null, { status: 204 }));
      return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    });
    renderHome();
    fireEvent.click(await screen.findByRole("button", { name: "Schutzbrillen" }));
    await screen.findByText("Brauche ich eine Schutzbrille?");

    fireEvent.click(screen.getByRole("button", { name: "Verlauf löschen" }));
    fireEvent.click(screen.getByRole("button", { name: "Endgültig löschen" }));

    await waitFor(() => expect(calls).toContain("POST /api/chat/new-session"));
    await waitFor(() =>
      expect(screen.queryByText("Brauche ich eine Schutzbrille?")).not.toBeInTheDocument(),
    );
  });

  it("does not call new-session when a non-active session is deleted", async () => {
    const calls: string[] = [];
    global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url === "/api/chat/current") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              session_id: "other",
              title: null,
              messages: [{ role: "user", content: "Aktive Frage", paragraphs: ["Aktive Frage"], citations: [] }],
            }),
            { status: 200 },
          ),
        );
      }
      if (url === "/api/chat/sessions" && !init?.method) {
        return Promise.resolve(new Response(JSON.stringify(sessionList), { status: 200 }));
      }
      if (init?.method === "DELETE") return Promise.resolve(new Response(null, { status: 204 }));
      return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    });
    renderHome();
    await screen.findByText("Aktive Frage");
    fireEvent.click(await screen.findByRole("button", { name: "Verlauf löschen" }));
    fireEvent.click(screen.getByRole("button", { name: "Endgültig löschen" }));

    await waitFor(() => expect(calls).toContain("DELETE /api/chat/sessions/sess-9"));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Schutzbrillen" })).not.toBeInTheDocument());
    expect(calls).not.toContain("POST /api/chat/new-session");
    expect(screen.getByText("Aktive Frage")).toBeInTheDocument();
  });

  it("does not append a late answer to a session opened in the meantime", async () => {
    let resolveAnswer: (response: Response) => void = () => {};
    global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/chat/current") return Promise.resolve(new Response(null, { status: 204 }));
      if (url === "/api/chat/sessions") {
        return Promise.resolve(new Response(JSON.stringify(sessionList), { status: 200 }));
      }
      if (url === "/api/chat/sessions/sess-9/messages") {
        return Promise.resolve(new Response(JSON.stringify(sessionMessages), { status: 200 }));
      }
      if (url === "/api/chat" && init?.method === "POST") {
        return new Promise<Response>((resolve) => {
          resolveAnswer = resolve;
        });
      }
      return Promise.resolve(new Response(JSON.stringify({ title: "T" }), { status: 200 }));
    });
    renderHome();
    fireEvent.change(screen.getByPlaceholderText("Frage stellen…"), { target: { value: "Frage" } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    fireEvent.click(await screen.findByRole("button", { name: "Schutzbrillen" }));
    await screen.findByText("Brauche ich eine Schutzbrille?");

    resolveAnswer(
      new Response(
        JSON.stringify({ session_id: "sess-old", answer: "Späte Antwort", answer_type: "fallback", paragraphs: ["Späte Antwort"], citations: [] }),
        { status: 200 },
      ),
    );
    await waitFor(() =>
      expect(
        (global.fetch as ReturnType<typeof vi.fn>).mock.calls.some(([u]) => u === "/api/chat/sessions/sess-old/title"),
      ).toBe(true),
    );
    expect(screen.queryByText("Späte Antwort")).not.toBeInTheDocument();
    expect(screen.getByText("Brauche ich eine Schutzbrille?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Schutzbrillen" })).toHaveAttribute("aria-current", "true");
  });

  it("starts a new chat when the jurisdiction changes while a session is open", async () => {
    const calls: string[] = [];
    global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url === "/api/chat/current") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              session_id: "sess-1",
              title: null,
              messages: [{ role: "user", content: "Aktive Frage", paragraphs: ["Aktive Frage"], citations: [] }],
            }),
            { status: 200 },
          ),
        );
      }
      if (url === "/api/chat/sessions") return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    });
    function SwitchToEu() {
      const { setJurisdiction } = useJurisdiction();
      return <button onClick={() => setJurisdiction("EU")}>to-eu</button>;
    }
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <SwitchToEu />
          <HomePageContent />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    await screen.findByText("Aktive Frage");
    expect(calls).not.toContain("POST /api/chat/new-session");

    fireEvent.click(screen.getByRole("button", { name: "to-eu" }));

    await waitFor(() => expect(calls).toContain("POST /api/chat/new-session"));
    await waitFor(() => expect(screen.queryByText("Aktive Frage")).not.toBeInTheDocument());
  });

  it("shows only this turn when the reply belongs to a different session than the active one", async () => {
    const calls: string[] = [];
    global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url === "/api/chat/current") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              session_id: "sess-old",
              title: null,
              messages: [{ role: "user", content: "Alte Frage", paragraphs: ["Alte Frage"], citations: [] }],
            }),
            { status: 200 },
          ),
        );
      }
      if (url === "/api/chat/sessions") return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      if (url === "/api/chat/sessions/sess-fresh/title") {
        return Promise.resolve(new Response(JSON.stringify({ title: "T" }), { status: 200 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({ session_id: "sess-fresh", answer: "Neue Antwort", answer_type: "fallback", paragraphs: ["Neue Antwort"], citations: [] }),
          { status: 200 },
        ),
      );
    });
    renderHome();
    await screen.findByText("Alte Frage");

    fireEvent.change(screen.getByPlaceholderText("Frage stellen…"), { target: { value: "Neue Frage" } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));

    expect(await screen.findByText("Neue Antwort")).toBeInTheDocument();
    expect(screen.getByText("Neue Frage")).toBeInTheDocument();
    expect(screen.queryByText("Alte Frage")).not.toBeInTheDocument();
    await waitFor(() => expect(calls).toContain("POST /api/chat/sessions/sess-fresh/title"));
  });

  it("shows a translated error message when the chat answer is an error", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/chat/current") return Promise.resolve(new Response(null, { status: 204 }));
      if (url === "/api/chat/sessions") return Promise.resolve(new Response(JSON.stringify([]), { status: 401 }));
      return Promise.resolve(new Response(JSON.stringify({ detail: "down" }), { status: 503 }));
    });
    renderHome();

    fireEvent.change(screen.getByPlaceholderText("Frage stellen…"), { target: { value: "Frage" } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));

    expect(
      await screen.findByText("Die Antwort konnte gerade nicht erstellt werden. Bitte versuche es erneut."),
    ).toBeInTheDocument();
  });
});
