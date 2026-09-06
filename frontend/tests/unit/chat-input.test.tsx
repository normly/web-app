// frontend/tests/unit/chat-input.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ChatInput } from "@/components/chat/chat-input";

function renderWithLocale(ui: React.ReactElement) {
  return render(<LocaleProvider initialLocale="de">{ui}</LocaleProvider>);
}

describe("ChatInput", () => {
  it("calls onSend with the typed message when the send button is clicked", () => {
    const onSend = vi.fn();
    renderWithLocale(<ChatInput onSend={onSend} disabled={false} />);
    const textbox = screen.getByPlaceholderText("Frage stellen…");
    fireEvent.change(textbox, { target: { value: "Ist DIN EN ISO 9001 gültig?" } });
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).toHaveBeenCalledWith("Ist DIN EN ISO 9001 gültig?");
  });

  it("calls onSend when Enter is pressed without Shift", () => {
    const onSend = vi.fn();
    renderWithLocale(<ChatInput onSend={onSend} disabled={false} />);
    const textbox = screen.getByPlaceholderText("Frage stellen…");
    fireEvent.change(textbox, { target: { value: "Frage" } });
    fireEvent.keyDown(textbox, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("Frage");
  });

  it("does not call onSend when Shift+Enter is pressed (newline instead)", () => {
    const onSend = vi.fn();
    renderWithLocale(<ChatInput onSend={onSend} disabled={false} />);
    const textbox = screen.getByPlaceholderText("Frage stellen…");
    fireEvent.change(textbox, { target: { value: "Frage" } });
    fireEvent.keyDown(textbox, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not call onSend while disabled (e.g. a request is in flight)", () => {
    const onSend = vi.fn();
    renderWithLocale(<ChatInput onSend={onSend} disabled={true} />);
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not call onSend for an empty message", () => {
    const onSend = vi.fn();
    renderWithLocale(<ChatInput onSend={onSend} disabled={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).not.toHaveBeenCalled();
  });
});
