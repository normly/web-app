// frontend/tests/unit/mode-toggle.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";

const setTheme = vi.fn();
const useThemeMock = vi.fn(() => ({ resolvedTheme: "light", setTheme }));
vi.mock("next-themes", () => ({
  useTheme: () => useThemeMock(),
}));

import { ModeToggle } from "@/components/mode-toggle";

describe("ModeToggle", () => {
  it("switches to dark mode when clicked while resolved theme is light", () => {
    useThemeMock.mockReturnValue({ resolvedTheme: "light", setTheme });
    render(
      <LocaleProvider initialLocale="de">
        <ModeToggle />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Farbschema umschalten" }));
    expect(setTheme).toHaveBeenCalledWith("dark");
  });

  it("switches to light mode when clicked while resolved theme is dark", () => {
    useThemeMock.mockReturnValue({ resolvedTheme: "dark", setTheme });
    render(
      <LocaleProvider initialLocale="de">
        <ModeToggle />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Farbschema umschalten" }));
    expect(setTheme).toHaveBeenCalledWith("light");
  });
});
