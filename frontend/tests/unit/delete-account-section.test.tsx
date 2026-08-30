// frontend/tests/unit/delete-account-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { DeleteAccountSection } from "@/components/account/delete-account-section";
import type { AccountSummary } from "@/lib/account-response";

const originalFetch = global.fetch;

const account: AccountSummary = {
  accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
  avatarDataUrl: null,
};

describe("DeleteAccountSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("only enables the delete button once the typed email matches the account email", () => {
    render(
      <LocaleProvider initialLocale="de">
        <DeleteAccountSection account={account} />
      </LocaleProvider>,
    );

    const deleteButton = screen.getByRole("button", { name: "Konto endgültig löschen" });
    expect(deleteButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Gib zur Bestätigung deine E-Mail-Adresse ein"), {
      target: { value: "wrong@example.de" },
    });
    expect(deleteButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Gib zur Bestätigung deine E-Mail-Adresse ein"), {
      target: { value: "a@example.de" },
    });
    expect(deleteButton).not.toBeDisabled();
  });

  it("submits the password and reloads the page on success", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "account_deleted" }), { status: 200 }),
    );
    const reloadSpy = vi.fn();
    vi.stubGlobal("location", { ...window.location, reload: reloadSpy });

    render(
      <LocaleProvider initialLocale="de">
        <DeleteAccountSection account={account} />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Gib zur Bestätigung deine E-Mail-Adresse ein"), {
      target: { value: "a@example.de" },
    });
    fireEvent.change(screen.getByLabelText("Passwort zur Bestätigung"), {
      target: { value: "correct horse" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Konto endgültig löschen" }));

    await waitFor(() => expect(reloadSpy).toHaveBeenCalled());
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ password: "correct horse" });
  });

  it("shows an error message when the backend rejects the password", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "password is incorrect" }), { status: 401 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <DeleteAccountSection account={account} />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Gib zur Bestätigung deine E-Mail-Adresse ein"), {
      target: { value: "a@example.de" },
    });
    fireEvent.change(screen.getByLabelText("Passwort zur Bestätigung"), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Konto endgültig löschen" }));

    await waitFor(() =>
      expect(
        screen.getByText("Konto konnte nicht gelöscht werden. Prüfe deine Eingaben."),
      ).toBeInTheDocument(),
    );
  });
});
