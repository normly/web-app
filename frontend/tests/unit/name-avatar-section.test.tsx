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
  avatarDataUrl: null,
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
});
