// frontend/tests/unit/page-header.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import * as React from "react";
import { render, screen } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { JurisdictionProvider } from "@/lib/jurisdiction/provider";
import { PageHeader } from "@/components/page-header";
import { SidebarProvider } from "@/components/ui/sidebar";

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light", setTheme: vi.fn() }),
}));

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

  it("renders the translated title", () => {
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    expect(screen.getByRole("heading", { name: "Chat" })).toBeInTheDocument();
  });

  it("renders no subtitle when subtitleKey is omitted", () => {
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    expect(screen.queryByText("Konto")).not.toBeInTheDocument();
  });

  it("shows the static no-notifications message in the bell popover", async () => {
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Benachrichtigungen" }));
    expect(await screen.findByText("Keine neuen Benachrichtigungen")).toBeInTheDocument();
  });

  it("renders the sidebar toggle button in its left cluster (Finding 1: the only sidebar toggle must live in PageHeader, not inside the Sidebar itself)", () => {
    renderPageHeader(<PageHeader titleKey="nav.chat" />);
    expect(screen.getByRole("button", { name: "Seitenleiste umschalten" })).toBeInTheDocument();
  });
});
