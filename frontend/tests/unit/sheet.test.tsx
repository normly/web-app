// frontend/tests/unit/sheet.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Sidebar, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { LocaleProvider, type Locale } from "@/lib/i18n/provider";

function renderOpenSheet(closeLabel?: string) {
  render(
    <Sheet open>
      <SheetContent closeLabel={closeLabel}>
        <SheetTitle>Title</SheetTitle>
        <SheetDescription>Description</SheetDescription>
      </SheetContent>
    </Sheet>,
  );
}

describe("SheetContent", () => {
  it("uses the closeLabel prop as the close button's accessible name", () => {
    renderOpenSheet("Fermer");
    expect(screen.getByRole("button", { name: "Fermer" })).toBeInTheDocument();
  });

  it("falls back to an English close label when no closeLabel is passed", () => {
    renderOpenSheet();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });
});

describe("Sidebar mobile sheet", () => {
  const originalInnerWidth = window.innerWidth;
  const originalMatchMedia = window.matchMedia;

  beforeEach(() => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: true,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    // useIsMobile() reads window.innerWidth against the 768px breakpoint.
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 500 });
  });

  afterEach(() => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: originalInnerWidth });
    window.matchMedia = originalMatchMedia;
  });

  function openMobileSidebar(locale: Locale) {
    render(
      <LocaleProvider initialLocale={locale}>
        <SidebarProvider>
          <SidebarTrigger />
          <Sidebar>
            <div>content</div>
          </Sidebar>
        </SidebarProvider>
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Toggle Sidebar" }));
  }

  it.each<[Locale, string]>([
    ["de", "Schließen"],
    ["en", "Close"],
  ])("labels the close button with the translated common.close (%s)", (locale, expected) => {
    openMobileSidebar(locale);
    expect(screen.getByRole("button", { name: expected })).toBeInTheDocument();
  });

  it.each<[Locale, string, string]>([
    ["de", "Seitenleiste", "Zeigt die mobile Seitenleiste an."],
    ["en", "Sidebar", "Displays the mobile sidebar."],
  ])("titles and describes the sheet dialog in the active locale (%s)", (locale, title, description) => {
    openMobileSidebar(locale);
    const dialog = screen.getByRole("dialog", { name: title });
    expect(dialog).toHaveAccessibleDescription(description);
  });
});
