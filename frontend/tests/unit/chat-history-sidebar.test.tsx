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

    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          { id: "1", session_token: "a", jurisdiction: "DE", language: "de", created_at: today.toISOString() },
          { id: "2", session_token: "b", jurisdiction: "DE", language: "de", created_at: yesterday.toISOString() },
          { id: "3", session_token: "c", jurisdiction: "DE", language: "de", created_at: sevenDaysAgo.toISOString() },
          { id: "4", session_token: "d", jurisdiction: "DE", language: "de", created_at: eightDaysAgo.toISOString() },
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
});
