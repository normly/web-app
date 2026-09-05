// frontend/tests/unit/mode-toggle.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const setTheme = vi.fn();
vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light", setTheme }),
}));

import { ModeToggle } from "@/components/mode-toggle";

describe("ModeToggle", () => {
  it("switches to dark mode when clicked while resolved theme is light", () => {
    render(<ModeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Farbschema umschalten" }));
    expect(setTheme).toHaveBeenCalledWith("dark");
  });
});
