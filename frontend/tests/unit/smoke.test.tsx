// frontend/tests/unit/smoke.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { JurisdictionProvider } from "@/lib/jurisdiction/provider";
import HomePage from "@/app/page";

const originalFetch = global.fetch;

describe("HomePage", () => {
  beforeEach(() => {
    // jsdom has no matchMedia -- AppShell's sidebar primitive's internal
    // useIsMobile() hook calls it on every render.
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

  it("renders without crashing", () => {
    // AppShell's user-footer checks /api/auth/session on mount, (since
    // ChatShell wires in ChatHistorySidebar) HomePageContent also fires
    // /api/chat/sessions on mount, and PageHeader's bell popover now fires
    // /api/account/notifications on mount too -- route by URL so each gets
    // its own Response instance instead of racing to read one shared body
    // twice, and so /api/account/notifications gets an array (not the
    // account-session shape) since useNotifications() calls .filter() on it
    // unconditionally.
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/chat/sessions") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 401 }));
      }
      if (url === "/api/account/notifications") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ account: null })));
    });
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <HomePage />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    expect(screen.getByPlaceholderText("Frage stellen…")).toBeInTheDocument();
  });

  it("renders exactly one <main> landmark (Finding 2: SidebarInset already renders one; page content must not nest a second)", () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/chat/sessions") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 401 }));
      }
      if (url === "/api/account/notifications") {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ account: null })));
    });
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <HomePage />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    expect(document.querySelectorAll("main")).toHaveLength(1);
  });

  // The old AppHeader's "Verlauf" link to /chats is gone now that HomePage is
  // wrapped in AppShell: its sidebar deliberately renders only Chat and
  // Suche (see app-shell.test.tsx). The standalone /chats route itself has
  // since been retired -- the chat page was rebuilt with a nested history
  // sidebar (see ChatShell/ChatHistorySidebar) that replaces it.
});
