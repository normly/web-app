// frontend/tests/unit/avatar.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Avatar } from "@/components/ui/avatar";

describe("Avatar", () => {
  it("renders an img pointed at the avatar endpoint when hasAvatar is true", () => {
    render(<Avatar hasAvatar firstName="Jamie" lastName="Tester" email="a@example.de" />);
    expect(screen.getByRole("img")).toHaveAttribute("src", "/api/account/avatar");
  });

  it("includes the avatarVersion as a cache-busting query param when set", () => {
    render(
      <Avatar
        hasAvatar avatarVersion={3} firstName="Jamie" lastName="Tester" email="a@example.de"
      />,
    );
    expect(screen.getByRole("img")).toHaveAttribute("src", "/api/account/avatar?v=3");
  });

  it("falls back to initials when the image fails to load", () => {
    render(<Avatar hasAvatar firstName="Jamie" lastName="Tester" email="a@example.de" />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByText("JT")).toBeInTheDocument();
  });

  it("falls back to the first letter of the email when no name is set", () => {
    render(<Avatar hasAvatar firstName={null} lastName={null} email="a@example.de" />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByText("A")).toBeInTheDocument();
  });

  it("renders initials directly without attempting an image when hasAvatar is false", () => {
    render(
      <Avatar hasAvatar={false} firstName="Jamie" lastName="Tester" email="a@example.de" />,
    );
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("JT")).toBeInTheDocument();
  });
});
