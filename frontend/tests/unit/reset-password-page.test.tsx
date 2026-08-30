// frontend/tests/unit/reset-password-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ResetPasswordContent } from "@/app/reset-password/reset-password-content";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("token=valid-token"),
}));

const originalFetch = global.fetch;

describe("ResetPasswordContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("submits the new password with the token from the URL", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "password_changed" }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <ResetPasswordContent />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Neues Passwort"), {
      target: { value: "new secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Passwort festlegen" }));

    await waitFor(() =>
      expect(
        screen.getByText("Dein Passwort wurde geändert. Du kannst dich jetzt anmelden."),
      ).toBeInTheDocument(),
    );
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ token: "valid-token", new_password: "new secret" });
  });

  it("shows an error message on an invalid token response", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <ResetPasswordContent />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Neues Passwort"), {
      target: { value: "new secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Passwort festlegen" }));

    await waitFor(() =>
      expect(screen.getByText("Dieser Link ist ungültig oder abgelaufen.")).toBeInTheDocument(),
    );
  });
});
