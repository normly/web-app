// frontend/tests/unit/login-form.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { LoginForm } from "@/components/auth/login-form";

const originalFetch = global.fetch;

describe("LoginForm", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("submits email and password to the login route and calls onSuccess", async () => {
    const onSuccess = vi.fn();
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    render(
      <LocaleProvider initialLocale="de">
        <LoginForm onSuccess={onSuccess} />
      </LocaleProvider>,
    );

    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), {
      target: { value: "a@example.de" },
    });
    fireEvent.change(screen.getByLabelText("Passwort"), {
      target: { value: "correct horse battery staple" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Anmelden" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/auth/login",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("shows a generic error message on a failed login without calling onSuccess", async () => {
    const onSuccess = vi.fn();
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ detail: "invalid" }), { status: 401 }));

    render(
      <LocaleProvider initialLocale="de">
        <LoginForm onSuccess={onSuccess} />
      </LocaleProvider>,
    );

    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), {
      target: { value: "a@example.de" },
    });
    fireEvent.change(screen.getByLabelText("Passwort"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "Anmelden" }));

    await waitFor(() =>
      expect(screen.getByText("Das hat leider nicht funktioniert. Bitte versuche es erneut.")).toBeInTheDocument(),
    );
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("switches to the reset-request view and back", async () => {
    render(
      <LocaleProvider initialLocale="de">
        <LoginForm onSuccess={vi.fn()} />
      </LocaleProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Passwort vergessen?" }));
    expect(screen.getByRole("button", { name: "Anmeldelink senden" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Zurück zur Anmeldung" }));
    expect(screen.getByRole("button", { name: "Anmelden" })).toBeInTheDocument();
  });
});
