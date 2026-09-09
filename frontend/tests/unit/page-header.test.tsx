// frontend/tests/unit/page-header.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import * as React from "react";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { JurisdictionProvider } from "@/lib/jurisdiction/provider";
import { PageHeader } from "@/components/page-header";
import { SidebarProvider } from "@/components/ui/sidebar";

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light", setTheme: vi.fn() }),
}));

const originalFetch = global.fetch;

// PageHeader renders a SidebarTrigger (Finding 1 of the app-shell final
// review), which needs SidebarContext from SidebarProvider -- in the real
// app that's supplied by AppShell, but PageHeader is tested in isolation
// here, so it must be provided directly.
function renderPageHeader(ui: React.ReactElement) {
  return render(
    <LocaleProvider initialLocale="de">
      <JurisdictionProvider initialJurisdiction="DE">
        <SidebarProvider>{ui}</SidebarProvider>
      </JurisdictionProvider>
    </LocaleProvider>,
  );
}

describe("PageHeader", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  beforeEach(() => {
    // jsdom has no matchMedia -- the sidebar primitive's internal
    // useIsMobile() hook calls it on every render.
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    // PageHeader now fetches notifications on mount (useNotifications) --
    // default every test to an empty list unless it overrides global.fetch
    // itself, so an unmocked fetch never throws in jsdom.
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
  });

  it("renders the translated title", () => {
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    expect(screen.getByRole("heading", { name: "Chat" })).toBeInTheDocument();
  });

  it("renders no subtitle when subtitleKey is omitted", () => {
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    expect(screen.queryByText("Konto")).not.toBeInTheDocument();
  });

  it("renders the sidebar toggle button in its left cluster (Finding 1: the only sidebar toggle must live in PageHeader, not inside the Sidebar itself)", () => {
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    expect(screen.getByRole("button", { name: "Seitenleiste umschalten" })).toBeInTheDocument();
  });

  it("shows the empty-notifications message when there are none", async () => {
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Benachrichtigungen" }));
    expect(await screen.findByText("Keine neuen Benachrichtigungen")).toBeInTheDocument();
  });

  it("shows the empty-notifications message for an anonymous visitor (401)", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "not authenticated" }), { status: 401 }),
    );
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Benachrichtigungen" }));
    expect(await screen.findByText("Keine neuen Benachrichtigungen")).toBeInTheDocument();
  });

  it("lists real notifications and marks one read on click", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "n1", workId: "w1", triggerType: "new_edition", triggerDocumentId: null,
              triggerJurisdiction: null, createdAt: "2026-01-01T00:00:00Z", readAt: null,
            },
          ]),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "n1", readAt: "2026-01-02T00:00:00Z" }), { status: 200 }),
      )
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Benachrichtigungen" }));
    const item = await screen.findByTestId("notification-n1");
    fireEvent.click(item);

    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/account/notifications/n1", expect.objectContaining({ method: "PATCH" }),
      ),
    );
  });

  it("shows an icon and a formatted date on each notification row", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "n1", workId: "w1", triggerType: "new_edition", triggerDocumentId: null,
            triggerJurisdiction: null, createdAt: "2026-01-15T00:00:00Z", readAt: null,
          },
        ]),
        { status: 200 },
      ),
    );

    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Benachrichtigungen" }));
    const item = await screen.findByTestId("notification-n1");

    expect(within(item).getByText("Ersetzt")).toBeInTheDocument();
    expect(within(item).getByText(new Date("2026-01-15T00:00:00Z").toLocaleDateString("de"))).toBeInTheDocument();
  });

  it("gives an unread notification a screen-reader-accessible 'Neu' label, not just a colored dot", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "n1", workId: "w1", triggerType: "new_edition", triggerDocumentId: null,
            triggerJurisdiction: null, createdAt: "2026-01-15T00:00:00Z", readAt: null,
          },
        ]),
        { status: 200 },
      ),
    );

    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Benachrichtigungen" }));
    const item = await screen.findByTestId("notification-n1");

    expect(within(item).getByText("Neu")).toBeInTheDocument();
  });
});
