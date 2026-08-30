// frontend/tests/unit/confirm-email-change-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ConfirmEmailChangeContent } from "@/app/confirm-email-change/confirm-email-change-content";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("token=valid-token&email=new@example.de"),
}));

const originalFetch = global.fetch;

describe("ConfirmEmailChangeContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("confirms the change on mount and shows a success message", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "email_changed" }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <ConfirmEmailChangeContent />
      </LocaleProvider>,
    );

    await waitFor(() =>
      expect(
        screen.getByText(
          "Deine E-Mail-Adresse wurde geändert. Du kannst dich jetzt mit der neuen Adresse anmelden.",
        ),
      ).toBeInTheDocument(),
    );
    const [calledUrl] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(calledUrl).toBe("/api/account/email/confirm?token=valid-token&email=new@example.de");
  });

  it("shows an error message on an invalid token", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <ConfirmEmailChangeContent />
      </LocaleProvider>,
    );

    await waitFor(() =>
      expect(screen.getByText("Dieser Bestätigungslink ist ungültig oder abgelaufen.")).toBeInTheDocument(),
    );
  });
});
