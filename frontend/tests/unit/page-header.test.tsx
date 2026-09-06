// frontend/tests/unit/page-header.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { JurisdictionProvider } from "@/lib/jurisdiction/provider";
import { PageHeader } from "@/components/page-header";

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light", setTheme: vi.fn() }),
}));

describe("PageHeader", () => {
  it("renders the translated title", () => {
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <PageHeader titleKey="nav.chat" />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    expect(screen.getByRole("heading", { name: "Chat" })).toBeInTheDocument();
  });

  it("renders no subtitle when subtitleKey is omitted", () => {
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <PageHeader titleKey="nav.chat" />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    expect(screen.queryByText("Konto")).not.toBeInTheDocument();
  });

  it("shows the static no-notifications message in the bell popover", () => {
    render(
      <LocaleProvider initialLocale="de">
        <JurisdictionProvider initialJurisdiction="DE">
          <PageHeader titleKey="nav.chat" />
        </JurisdictionProvider>
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Benachrichtigungen" }));
    expect(screen.getByText("Keine neuen Benachrichtigungen")).toBeInTheDocument();
  });
});
