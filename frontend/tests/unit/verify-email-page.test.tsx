// frontend/tests/unit/verify-email-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { VerifyEmailContent } from "@/app/verify-email/verify-email-content";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("token=valid-token"),
}));

const originalFetch = global.fetch;

describe("VerifyEmailContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the verified message when the token is accepted", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "email_verified" }), { status: 200 }),
    );
    render(
      <LocaleProvider initialLocale="de">
        <VerifyEmailContent />
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByText("Deine E-Mail-Adresse wurde bestätigt.")).toBeInTheDocument(),
    );
    expect(global.fetch).toHaveBeenCalledWith("/api/auth/verify-email?token=valid-token");
  });

  it("shows the invalid-link message and a resend form when the token is rejected", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
    );
    render(
      <LocaleProvider initialLocale="de">
        <VerifyEmailContent />
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByText("Dieser Link ist ungültig oder abgelaufen.")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Bestätigungslink erneut senden" })).toBeInTheDocument();
  });

  it("shows the resend-sent confirmation after submitting the resend form", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith("/api/auth/verify-email?")) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify({ status: "sent" }), { status: 200 }),
      );
    });
    render(
      <LocaleProvider initialLocale="de">
        <VerifyEmailContent />
      </LocaleProvider>,
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Bestätigungslink erneut senden" })).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), {
      target: { value: "a@example.de" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Bestätigungslink erneut senden" }));
    await waitFor(() =>
      expect(
        screen.getByText(
          "Falls ein Konto mit dieser Adresse existiert und noch nicht bestätigt ist, wurde eine E-Mail versendet.",
        ),
      ).toBeInTheDocument(),
    );
    const resendCall = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      ([url]) => url === "/api/auth/verify-email/resend",
    );
    expect(resendCall).toBeDefined();
  });
});
