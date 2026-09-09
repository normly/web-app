// frontend/tests/unit/name-avatar-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { NameAvatarSection } from "@/components/account/name-avatar-section";
import type { AccountSummary } from "@/lib/account-response";

const originalFetch = global.fetch;

const account: AccountSummary = {
  accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
  avatarDataUrl: null, hasPassword: true, notificationPreference: "immediate",
};

describe("NameAvatarSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("saves the entered first and last name", async () => {
    const onAccountUpdated = vi.fn();
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          accountId: "acc-1", email: "a@example.de", firstName: "Jamie", lastName: "Weber",
          avatarDataUrl: null,
        }),
        { status: 200 },
      ),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NameAvatarSection account={account} onAccountUpdated={onAccountUpdated} />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Vorname"), { target: { value: "Jamie" } });
    fireEvent.change(screen.getByLabelText("Nachname"), { target: { value: "Weber" } });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(onAccountUpdated).toHaveBeenCalled());
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ first_name: "Jamie", last_name: "Weber" });
  });

  it("shows a remove button only when an avatar is already set", () => {
    render(
      <LocaleProvider initialLocale="de">
        <NameAvatarSection account={account} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    expect(screen.queryByText("Bild entfernen")).not.toBeInTheDocument();
  });

  it("shows an error message when saving the name fails", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "something went wrong" }), { status: 500 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NameAvatarSection account={account} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Vorname"), { target: { value: "Jamie" } });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() =>
      expect(
        screen.getByText("Name konnte nicht gespeichert werden. Bitte versuche es erneut."),
      ).toBeInTheDocument(),
    );
  });

  it("shows an error message when an oversized avatar upload is rejected", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "avatar image exceeds 5MB" }), { status: 400 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NameAvatarSection account={account} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    const file = new File([new Uint8Array(10)], "avatar.png", { type: "image/png" });
    const input = screen.getByLabelText("Bild hochladen") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() =>
      expect(
        screen.getByText("Profilbild konnte nicht aktualisiert werden. Bitte versuche es erneut."),
      ).toBeInTheDocument(),
    );
  });

  it("shows an error message when the avatar upload request fails at the network level", async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError("network error"));

    render(
      <LocaleProvider initialLocale="de">
        <NameAvatarSection account={account} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    const file = new File([new Uint8Array(10)], "avatar.png", { type: "image/png" });
    const input = screen.getByLabelText("Bild hochladen") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() =>
      expect(
        screen.getByText("Profilbild konnte nicht aktualisiert werden. Bitte versuche es erneut."),
      ).toBeInTheDocument(),
    );
  });

  it("shows an error message when removing the avatar fails at the network level", async () => {
    const accountWithAvatar: AccountSummary = { ...account, avatarDataUrl: "data:image/png;base64,abc" };
    global.fetch = vi.fn().mockRejectedValue(new TypeError("network error"));

    render(
      <LocaleProvider initialLocale="de">
        <NameAvatarSection account={accountWithAvatar} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Bild entfernen" }));

    await waitFor(() =>
      expect(
        screen.getByText("Profilbild konnte nicht aktualisiert werden. Bitte versuche es erneut."),
      ).toBeInTheDocument(),
    );
  });
});
