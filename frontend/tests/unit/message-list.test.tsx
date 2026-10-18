// frontend/tests/unit/message-list.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { MessageList, type ChatMessageView } from "@/components/chat/message-list";

describe("MessageList", () => {
  it("renders paragraphs with their chips and whole-answer chips after them", () => {
    const messages: ChatMessageView[] = [
      { role: "user", content: "Was gilt beim Schweißen?" },
      {
        role: "assistant",
        content: "Erster Absatz.\n\nZweiter Absatz.",
        paragraphs: [
          {
            text: "Erster Absatz.",
            citations: [{ documentId: "d1", segmentId: "s1", designation: "DGUV Vorschrift 1", section: "§ 2" }],
          },
          { text: "Zweiter Absatz.", citations: [] },
        ],
        answerCitations: [{ documentId: "d2", segmentId: null, designation: "ISO 9001", section: null }],
      },
    ];
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={messages} isLoading={false} />
      </LocaleProvider>,
    );

    expect(screen.getByText("Was gilt beim Schweißen?")).toBeInTheDocument();
    expect(screen.getByText("Erster Absatz.")).toBeInTheDocument();
    expect(screen.getByText("Zweiter Absatz.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "DGUV Vorschrift 1 · § 2" })).toHaveAttribute(
      "href",
      "/documents/d1#segment-s1",
    );
    expect(screen.getByRole("link", { name: "ISO 9001" })).toHaveAttribute("href", "/documents/d2");
  });

  it("shows a loading indicator when isLoading is true", () => {
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={[]} isLoading={true} />
      </LocaleProvider>,
    );
    expect(screen.getByText("Antwort wird geladen…")).toBeInTheDocument();
  });

  it("renders an assistant message without chips when it has no citations", () => {
    const messages: ChatMessageView[] = [
      {
        role: "assistant",
        content: "Fallback-Antwort ohne Quelle.",
        paragraphs: [{ text: "Fallback-Antwort ohne Quelle.", citations: [] }],
        answerCitations: [],
      },
    ];
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={messages} isLoading={false} />
      </LocaleProvider>,
    );
    expect(screen.getByText("Fallback-Antwort ohne Quelle.")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  describe("copy button", () => {
    let originalClipboard: Clipboard;

    beforeEach(() => {
      originalClipboard = navigator.clipboard;
    });

    afterEach(() => {
      Object.defineProperty(navigator, "clipboard", {
        value: originalClipboard,
        writable: true,
      });
    });

    it("copies the assistant message to the clipboard when the copy button is clicked", async () => {
      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText },
        writable: true,
      });
      const messages: ChatMessageView[] = [
        { role: "assistant", content: "DIN EN ISO 9001 ist noch gültig." },
      ];
      render(
        <LocaleProvider initialLocale="de">
          <MessageList messages={messages} isLoading={false} />
        </LocaleProvider>,
      );
      fireEvent.click(screen.getByRole("button", { name: "Antwort kopieren" }));
      expect(writeText).toHaveBeenCalledWith("DIN EN ISO 9001 ist noch gültig.");
    });

    it("shows copied confirmation state and reverts after timeout", async () => {
      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText },
        writable: true,
      });
      const messages: ChatMessageView[] = [
        { role: "assistant", content: "DIN EN ISO 9001 ist noch gültig." },
      ];
      render(
        <LocaleProvider initialLocale="de">
          <MessageList messages={messages} isLoading={false} />
        </LocaleProvider>,
      );
      const button = screen.getByRole("button", { name: "Antwort kopieren" });
      fireEvent.click(button);
      // Wait for the copied state to appear after clipboard API completes
      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Kopiert" })).toBeInTheDocument();
      });
      // Wait for the timeout to revert the copied state (2000ms with real timers)
      await waitFor(
        () => {
          expect(screen.getByRole("button", { name: "Antwort kopieren" })).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });
  });

  it("does not render a copy button next to a user message", () => {
    const messages: ChatMessageView[] = [{ role: "user", content: "Ist DIN EN ISO 9001 gültig?" }];
    render(
      <LocaleProvider initialLocale="de">
        <MessageList messages={messages} isLoading={false} />
      </LocaleProvider>,
    );
    expect(screen.queryByRole("button", { name: "Antwort kopieren" })).not.toBeInTheDocument();
  });
});
