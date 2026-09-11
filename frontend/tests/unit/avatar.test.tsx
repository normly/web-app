// frontend/tests/unit/avatar.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Avatar } from "@/components/ui/avatar";

describe("Avatar", () => {
  it("renders an img pointed at the avatar endpoint", () => {
    render(<Avatar firstName="Jamie" lastName="Weber" email="a@example.de" />);
    expect(screen.getByRole("img")).toHaveAttribute("src", "/api/account/avatar");
  });

  it("includes the avatarVersion as a cache-busting query param when set", () => {
    render(
      <Avatar avatarVersion={3} firstName="Jamie" lastName="Weber" email="a@example.de" />,
    );
    expect(screen.getByRole("img")).toHaveAttribute("src", "/api/account/avatar?v=3");
  });

  it("falls back to initials when the image fails to load", () => {
    render(<Avatar firstName="Jamie" lastName="Weber" email="a@example.de" />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByText("JW")).toBeInTheDocument();
  });

  it("falls back to the first letter of the email when no name is set", () => {
    render(<Avatar firstName={null} lastName={null} email="a@example.de" />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByText("A")).toBeInTheDocument();
  });
});
