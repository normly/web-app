// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Pagination } from "@/components/ui/pagination";

describe("Pagination", () => {
  it("disables Previous on the first page and enables Next when more results remain", () => {
    const onPageChange = vi.fn();
    render(
      <Pagination
        offset={0}
        limit={20}
        total={45}
        onPageChange={onPageChange}
        previousLabel="Zurück"
        nextLabel="Weiter"
      />,
    );
    expect(screen.getByRole("button", { name: "Zurück" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Weiter" })).not.toBeDisabled();
  });

  it("calls onPageChange with the next offset when Next is clicked", () => {
    const onPageChange = vi.fn();
    render(
      <Pagination
        offset={0}
        limit={20}
        total={45}
        onPageChange={onPageChange}
        previousLabel="Zurück"
        nextLabel="Weiter"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Weiter" }));
    expect(onPageChange).toHaveBeenCalledWith(20);
  });

  it("disables Next on the last page", () => {
    const onPageChange = vi.fn();
    render(
      <Pagination
        offset={40}
        limit={20}
        total={45}
        onPageChange={onPageChange}
        previousLabel="Zurück"
        nextLabel="Weiter"
      />,
    );
    expect(screen.getByRole("button", { name: "Weiter" })).toBeDisabled();
  });
});
