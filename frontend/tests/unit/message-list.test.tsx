// frontend/tests/unit/message-list.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { MessageList, type ChatMessageView } from "@/components/chat/message-list";

describe("MessageList", () => {
  it("renders user and assistant messages with a citation link", () => {
    const messages: ChatMessageView[] = [
      { role: "user", content: "Ist DIN EN ISO 9001 gültig?" },
      {
        role: "assistant",
        content: "DIN EN ISO 9001 ist noch gültig.",
        citations: [{ documentId: "11111111-1111-1111-1111-111111111111", href: "https://example.de/norm" }],
      },
    ];
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={messages} isLoading={false} />
      </LocaleProvider>,
    );
    expect(screen.getByText("Ist DIN EN ISO 9001 gültig?")).toBeInTheDocument();
    expect(screen.getByText("DIN EN ISO 9001 ist noch gültig.")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "https://example.de/norm");
  });

  it("shows a loading indicator when isLoading is true", () => {
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={[]} isLoading={true} />
      </LocaleProvider>,
    );
    expect(screen.getByText("Antwort wird geladen…")).toBeInTheDocument();
  });

  it("renders an assistant message without a citation link when resolution failed", () => {
    const messages: ChatMessageView[] = [
      { role: "assistant", content: "Fallback-Antwort ohne Quelle.", citations: [] },
    ];
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={messages} isLoading={false} />
      </LocaleProvider>,
    );
    expect(screen.getByText("Fallback-Antwort ohne Quelle.")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
