// frontend/tests/unit/chat-history-sidebar.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ChatHistorySidebar } from "@/components/chat/chat-history-sidebar";

const originalFetch = global.fetch;

function renderSidebar(onNewChat = vi.fn()) {
  return render(
    <LocaleProvider initialLocale="de">
      <ChatHistorySidebar onNewChat={onNewChat} />
    </LocaleProvider>,
  );
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

  it("groups sessions into Heute/Gestern/Vor 7 Tagen/Älter buckets", async () => {
    const now = new Date();
    const today = new Date(now);
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const fourDaysAgo = new Date(now);
    fourDaysAgo.setDate(fourDaysAgo.getDate() - 4);
    const twoWeeksAgo = new Date(now);
    twoWeeksAgo.setDate(twoWeeksAgo.getDate() - 14);

    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          { id: "1", session_token: "a", jurisdiction: "DE", language: "de", created_at: today.toISOString() },
          { id: "2", session_token: "b", jurisdiction: "DE", language: "de", created_at: yesterday.toISOString() },
          { id: "3", session_token: "c", jurisdiction: "DE", language: "de", created_at: fourDaysAgo.toISOString() },
          { id: "4", session_token: "d", jurisdiction: "DE", language: "de", created_at: twoWeeksAgo.toISOString() },
        ]),
        { status: 200 },
      ),
    );
    renderSidebar();
    await waitFor(() => expect(screen.getByText("Heute")).toBeInTheDocument());
    expect(screen.getByText("Gestern")).toBeInTheDocument();
    expect(screen.getByText("Vor 7 Tagen")).toBeInTheDocument();
    expect(screen.getByText("Älter")).toBeInTheDocument();
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
