// frontend/tests/unit/home-page-content.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { HomePageContent } from "@/app/home-page-content";

const originalFetch = global.fetch;

describe("HomePageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("sends the current UI locale as the chat language, not a hardcoded 'de'", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ answer: "Answer", answer_type: "fallback", citations: [] }),
        { status: 200 },
      ),
    );
    render(
      <LocaleProvider initialLocale="en">
        <HomePageContent />
      </LocaleProvider>,
    );

    fireEvent.change(screen.getByPlaceholderText("Ask a question…"), {
      target: { value: "Is DIN EN ISO 9001 valid?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(init.body as string);
    expect(body.language).toBe("en");
  });
});
