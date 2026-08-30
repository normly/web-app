// frontend/tests/unit/email-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { EmailSection } from "@/components/account/email-section";
import type { AccountSummary } from "@/lib/account-response";

const originalFetch = global.fetch;

const account: AccountSummary = {
  accountId: "acc-1", email: "old@example.de", firstName: null, lastName: null,
  avatarDataUrl: null,
};

describe("EmailSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the current email and requests a change for a new one", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "confirmation_sent" }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <EmailSection account={account} />
      </LocaleProvider>,
    );

    expect(screen.getByText("old@example.de")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Neue E-Mail-Adresse"), {
      target: { value: "new@example.de" },
    });
    fireEvent.click(screen.getByRole("button", { name: "E-Mail-Adresse ändern" }));

    await waitFor(() =>
      expect(
        screen.getByText("Bestätigungslink wurde an die neue Adresse gesendet."),
      ).toBeInTheDocument(),
    );
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ new_email: "new@example.de" });
  });

  it("shows an error message when the request fails", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "an account already exists for this email" }), {
        status: 409,
      }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <EmailSection account={account} />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Neue E-Mail-Adresse"), {
      target: { value: "taken@example.de" },
    });
    fireEvent.click(screen.getByRole("button", { name: "E-Mail-Adresse ändern" }));

    await waitFor(() =>
      expect(screen.getByText("Etwas ist schiefgelaufen. Bitte versuche es erneut.")).toBeInTheDocument(),
    );
  });
});
