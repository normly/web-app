// frontend/tests/unit/chat-history-sidebar.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { SidebarProvider } from "@/components/ui/sidebar";
import { ChatHistorySidebar } from "@/components/chat/chat-history-sidebar";

const originalFetch = global.fetch;

function renderSidebar(onNewChat = vi.fn()) {
  return render(
    <LocaleProvider initialLocale="de">
      {/* ChatHistorySidebar itself renders bare <Sidebar>, no provider of
          its own -- it is always composed as a sibling of SidebarInset
          under one shared SidebarProvider (see ChatShell, Task 5), so
          tests supply that provider here instead. */}
      <SidebarProvider>
        <ChatHistorySidebar onNewChat={onNewChat} />
      </SidebarProvider>
    </LocaleProvider>,
  );
}

// Builds a Date for exactly `n` calendar days before `base`, at a fixed
// time of day (noon). Using calendar-day arithmetic on the constructor
// fields (not raw millisecond subtraction) means this always lands on the
// intended calendar date relative to "today" regardless of what time of
// day the test happens to run at -- consistent with how the component
// itself buckets by calendar day, not by a rolling 24h window.
function daysAgoAtNoon(base: Date, n: number): Date {
  return new Date(base.getFullYear(), base.getMonth(), base.getDate() - n, 12, 0, 0, 0);
}

function findGroupContaining(labelText: string): HTMLElement {
  const label = screen.getByText(labelText);
  const group = label.closest('[data-sidebar="group"]');
  if (!group) {
    throw new Error(`no [data-sidebar="group"] ancestor found for label "${labelText}"`);
  }
  return group as HTMLElement;
}

describe("ChatHistorySidebar", () => {
  beforeEach(() => {
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

  it("shows the login-required message when there is no account session", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 401 }));
    renderSidebar();
    await waitFor(() =>
      expect(screen.getByText("Melde dich an, um deinen Chat-Verlauf zu sehen.")).toBeInTheDocument(),
    );
  });

  it("shows the empty message when logged in with no sessions", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    renderSidebar();
    await waitFor(() =>
      expect(screen.getByText("Noch keine Chats vorhanden.")).toBeInTheDocument(),
    );
  });

  it("groups sessions into Heute/Gestern/Vor 7 Tagen/Älter buckets, including the exact 7-day boundary", async () => {
    const now = new Date();
    const today = new Date(now);
    const yesterday = daysAgoAtNoon(now, 1);
    // Boundary pair: exactly 7 calendar days ago must still be "Vor 7
    // Tagen", exactly 8 calendar days ago must already be "Älter". A
    // rolling 24h*7 window (the original, buggy implementation) can put
    // these two on the wrong side of the line depending on what time of
    // day `now` is; the fixed, calendar-day-normalized implementation
    // must not.
    const sevenDaysAgo = daysAgoAtNoon(now, 7);
    const eightDaysAgo = daysAgoAtNoon(now, 8);

    const todayText = today.toLocaleString("de");
    const yesterdayText = yesterday.toLocaleString("de");
    const sevenDaysAgoText = sevenDaysAgo.toLocaleString("de");
    const eightDaysAgoText = eightDaysAgo.toLocaleString("de");

    const sessionTokens = [
      "session-token-alpha-001",
      "session-token-beta-002",
      "session-token-gamma-003",
      "session-token-delta-004",
    ];

    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          { id: "1", session_token: sessionTokens[0], jurisdiction: "DE", language: "de", created_at: today.toISOString() },
          { id: "2", session_token: sessionTokens[1], jurisdiction: "DE", language: "de", created_at: yesterday.toISOString() },
          { id: "3", session_token: sessionTokens[2], jurisdiction: "DE", language: "de", created_at: sevenDaysAgo.toISOString() },
          { id: "4", session_token: sessionTokens[3], jurisdiction: "DE", language: "de", created_at: eightDaysAgo.toISOString() },
        ]),
        { status: 200 },
      ),
    );
    renderSidebar();
    await waitFor(() => expect(screen.getByText("Heute")).toBeInTheDocument());
    expect(screen.getByText("Gestern")).toBeInTheDocument();
    expect(screen.getByText("Vor 7 Tagen")).toBeInTheDocument();
    expect(screen.getByText("Älter")).toBeInTheDocument();

    // Each session's rendered date/time text must appear inside its
    // expected bucket, not merely somewhere in the document -- this is
    // what actually pins the bucketing boundary, as opposed to only
    // checking that the four bucket labels exist.
    expect(within(findGroupContaining("Heute")).getByText(todayText)).toBeInTheDocument();
    expect(within(findGroupContaining("Gestern")).getByText(yesterdayText)).toBeInTheDocument();
    expect(within(findGroupContaining("Vor 7 Tagen")).getByText(sevenDaysAgoText)).toBeInTheDocument();
    expect(within(findGroupContaining("Älter")).getByText(eightDaysAgoText)).toBeInTheDocument();

    // History items are genuinely non-interactive -- no click-to-resume,
    // ever (see Global Constraints) -- so there must be no <a> anywhere
    // in the sidebar.
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    // The raw session_token must never leak into the rendered DOM: only
    // the formatted created_at timestamp is shown, never the credential
    // itself. Checking the whole body's innerHTML (not just the sidebar
    // subtree) is deliberate -- it also catches a leak via a stray
    // data-* attribute, title, or anywhere else in the tree, not only
    // visible text.
    for (const token of sessionTokens) {
      expect(document.body.innerHTML).not.toContain(token);
    }
  });

  it("calls onNewChat and the new-session endpoint when the button is clicked", async () => {
    const onNewChat = vi.fn();
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 401 }));
    renderSidebar(onNewChat);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith("/api/chat/sessions"));
    fireEvent.click(screen.getByRole("button", { name: "Neuer Chat" }));
    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith("/api/chat/new-session", { method: "POST" }),
    );
    expect(onNewChat).toHaveBeenCalled();
  });

  // Distinct, fixed timestamps: the list is sorted newest first, so s-1 is
  // always the first entry (identical new Date() values made this flaky).
  const baseTime = Date.now();
  const twoSessions = [
    { id: "s-1", session_token: "tok-one", jurisdiction: "DE", language: "de", created_at: new Date(baseTime).toISOString() },
    { id: "s-2", session_token: "tok-two", jurisdiction: "DE", language: "de", created_at: new Date(baseTime - 60_000).toISOString() },
  ];

  function mockFetch(deleteResponse: () => Response) {
    global.fetch = vi.fn().mockImplementation((url: string, init?: { method?: string }) => {
      if (init?.method === "DELETE") return Promise.resolve(deleteResponse());
      return Promise.resolve(new Response(JSON.stringify(twoSessions), { status: 200 }));
    });
  }

  it("deletes one entry only after confirmation and removes it from the list", async () => {
    mockFetch(() => new Response(null, { status: 204 }));
    renderSidebar();
    const buttons = await screen.findAllByRole("button", { name: "Verlauf löschen" });
    expect(buttons).toHaveLength(2);

    fireEvent.click(buttons[0]);
    expect(global.fetch).not.toHaveBeenCalledWith(
      "/api/chat/sessions/s-1", expect.anything(),
    );
    fireEvent.click(await screen.findByRole("button", { name: "Endgültig löschen" }));

    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith("/api/chat/sessions/s-1", { method: "DELETE" }),
    );
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Verlauf löschen" })).toHaveLength(1),
    );
  });

  it("does not delete when the confirmation is cancelled", async () => {
    mockFetch(() => new Response(null, { status: 204 }));
    renderSidebar();
    const buttons = await screen.findAllByRole("button", { name: "Verlauf löschen" });
    fireEvent.click(buttons[0]);
    fireEvent.click(await screen.findByRole("button", { name: "Abbrechen" }));
    expect(global.fetch).not.toHaveBeenCalledWith(
      "/api/chat/sessions/s-1", expect.anything(),
    );
    expect(screen.getAllByRole("button", { name: "Verlauf löschen" })).toHaveLength(2);
  });

  it("deletes all histories after confirmation and shows the empty state", async () => {
    mockFetch(() => new Response(JSON.stringify({ deleted: 2 }), { status: 200 }));
    renderSidebar();
    await screen.findAllByRole("button", { name: "Verlauf löschen" });

    fireEvent.click(screen.getByRole("button", { name: "Alle Verläufe löschen" }));
    fireEvent.click(await screen.findByRole("button", { name: "Endgültig löschen" }));

    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith("/api/chat/sessions", { method: "DELETE" }),
    );
    await waitFor(() =>
      expect(screen.getByText("Noch keine Chats vorhanden.")).toBeInTheDocument(),
    );
  });

  it("leaves the list unchanged when the backend refuses the deletion", async () => {
    mockFetch(() => new Response(JSON.stringify({ detail: "x" }), { status: 500 }));
    renderSidebar();
    const buttons = await screen.findAllByRole("button", { name: "Verlauf löschen" });
    fireEvent.click(buttons[0]);
    fireEvent.click(await screen.findByRole("button", { name: "Endgültig löschen" }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    // The modal dialog hides the rest of the page from the a11y tree.
    expect(
      screen.getAllByRole("button", { name: "Verlauf löschen", hidden: true }),
    ).toHaveLength(2);
  });

  it("offers no delete-all action when there are no sessions", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    renderSidebar();
    await screen.findByText("Noch keine Chats vorhanden.");
    expect(screen.queryByRole("button", { name: "Alle Verläufe löschen" })).not.toBeInTheDocument();
  });
});
