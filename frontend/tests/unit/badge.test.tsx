// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "@/components/ui/badge";

describe("Badge", () => {
  it("renders its children", () => {
    render(<Badge>Gültig</Badge>);
    expect(screen.getByText("Gültig")).toBeInTheDocument();
  });

  it("applies the outline variant's classes", () => {
    render(<Badge variant="outline">Ersetzt</Badge>);
    expect(screen.getByText("Ersetzt")).toHaveClass("border");
  });
});
