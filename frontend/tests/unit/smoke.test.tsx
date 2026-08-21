// frontend/tests/unit/smoke.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import HomePage from "@/app/page";

describe("HomePage", () => {
  it("renders without crashing", () => {
    render(
      <LocaleProvider initialLocale="de">
        <HomePage />
      </LocaleProvider>,
    );
    expect(screen.getByPlaceholderText("Frage stellen…")).toBeInTheDocument();
  });
});
