// frontend/tests/unit/app-shell.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { AppShell } from "@/components/app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

const originalFetch = global.fetch;

describe("AppShell", () => {
  beforeEach(() => {
    // jsdom has no matchMedia -- the sidebar primitive's internal
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

  it("renders exactly the Chat and Suche nav links, nothing else", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <AppShell instanceName="normly" logoPath={null}>
          <div>content</div>
        </AppShell>
      </LocaleProvider>,
    );
    expect(screen.getByRole("link", { name: "Chat" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Suche" })).toHaveAttribute("href", "/search");
    expect(screen.getAllByRole("link")).toHaveLength(2);
  });

  it("shows the login trigger in the footer when logged out", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <AppShell instanceName="normly" logoPath={null}>
          <div>content</div>
        </AppShell>
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Anmelden" })).toBeInTheDocument(),
    );
  });

  it("shows the account email and a logout item when logged in", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          account: {
            accountId: "1", email: "a@example.de", firstName: null, lastName: null,
            avatarDataUrl: null,
          },
        }),
      ),
    );
    render(
      <LocaleProvider initialLocale="de">
        <AppShell instanceName="normly" logoPath={null}>
          <div>content</div>
        </AppShell>
      </LocaleProvider>,
    );
    await waitFor(() => expect(screen.getByText("a@example.de")).toBeInTheDocument());
  });

  it("renders the children inside the sidebar inset", () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    render(
      <LocaleProvider initialLocale="de">
        <AppShell instanceName="normly" logoPath={null}>
          <div>page content</div>
        </AppShell>
      </LocaleProvider>,
    );
    expect(screen.getByText("page content")).toBeInTheDocument();
  });

  it("does not render a SidebarTrigger itself (Finding 1: the only toggle must live in PageHeader, in SidebarInset -- one rendered inside the Sidebar it opens is unreachable on mobile)", () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ account: null })));
    const { container } = render(
      <LocaleProvider initialLocale="de">
        <AppShell instanceName="normly" logoPath={null}>
          <div>content</div>
        </AppShell>
      </LocaleProvider>,
    );
    // Distinguished from SidebarRail (also a <button>, also toggles the
    // sidebar, also carries a German aria-label) by SidebarTrigger's own
    // data-sidebar="trigger" marker -- an accessible-name query here would
    // ambiguously match the rail too.
    expect(container.querySelector('[data-sidebar="trigger"]')).not.toBeInTheDocument();
  });
});
