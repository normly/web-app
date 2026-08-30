// frontend/tests/unit/password-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { PasswordSection } from "@/components/account/password-section";

const originalFetch = global.fetch;

describe("PasswordSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("submits the current and new password and shows a success message", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "password_set" }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <PasswordSection />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Aktuelles Passwort"), {
      target: { value: "old secret" },
    });
    fireEvent.change(screen.getByLabelText("Neues Passwort"), {
      target: { value: "new secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Passwort ändern" }));

    await waitFor(() =>
      expect(screen.getByText("Dein Passwort wurde geändert.")).toBeInTheDocument(),
    );
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      current_password: "old secret", new_password: "new secret",
    });
  });

  it("sends null for an empty current-password field", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "password_set" }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <PasswordSection />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Neues Passwort"), {
      target: { value: "new secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Passwort ändern" }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ current_password: null, new_password: "new secret" });
  });

  it("shows an error message on a 401 response", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "current password is incorrect" }), { status: 401 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <PasswordSection />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Aktuelles Passwort"), {
      target: { value: "wrong" },
    });
    fireEvent.change(screen.getByLabelText("Neues Passwort"), { target: { value: "new secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Passwort ändern" }));

    await waitFor(() =>
      expect(screen.getByText("Das aktuelle Passwort ist falsch.")).toBeInTheDocument(),
    );
  });
});
