// frontend/tests/unit/avatar.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Avatar } from "@/components/ui/avatar";

describe("Avatar", () => {
  it("renders the image when avatarDataUrl is set", () => {
    render(
      <Avatar
        avatarDataUrl="data:image/jpeg;base64,xyz" firstName="Jamie" lastName="Weber"
        email="a@example.de"
      />,
    );
    expect(screen.getByRole("img")).toHaveAttribute("src", "data:image/jpeg;base64,xyz");
  });

  it("renders both initials when first and last name are set", () => {
    render(
      <Avatar avatarDataUrl={null} firstName="Jamie" lastName="Weber" email="a@example.de" />,
    );
    expect(screen.getByText("JW")).toBeInTheDocument();
  });

  it("falls back to the first letter of the email when no name is set", () => {
    render(<Avatar avatarDataUrl={null} firstName={null} lastName={null} email="a@example.de" />);
    expect(screen.getByText("A")).toBeInTheDocument();
  });
});
