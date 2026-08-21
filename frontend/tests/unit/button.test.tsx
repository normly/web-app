// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("renders its label and calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Absenden</Button>);
    const button = screen.getByRole("button", { name: "Absenden" });
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is disabled and unclickable when the disabled prop is set", () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} disabled>
        Absenden
      </Button>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Absenden" }));
    expect(onClick).not.toHaveBeenCalled();
  });
});
