// frontend/tests/unit/notification-preference-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { NotificationPreferenceSection } from "@/components/account/notification-preference-section";
import type { AccountSummary } from "@/lib/account-response";

const originalFetch = global.fetch;

const account: AccountSummary = {
  accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
  avatarDataUrl: null, hasPassword: true, notificationPreference: "none",
};

describe("NotificationPreferenceSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("saves the selected preference", async () => {
    const onAccountUpdated = vi.fn();
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...account, notificationPreference: "both" }), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={account} onAccountUpdated={onAccountUpdated} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByLabelText("Software und E-Mail"));

    await waitFor(() => expect(onAccountUpdated).toHaveBeenCalled());
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ notification_preference: "both" });
  });

  it("disables the options while a save is in flight", async () => {
    // Without this guard, rapid clicking between options fires several
    // PATCHes that can resolve out of order, leaving the UI showing a
    // preference the server does not hold.
    let resolveFetch: ((response: Response) => void) | undefined;
    global.fetch = vi.fn().mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={account} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByLabelText("Software und E-Mail"));

    await waitFor(() => expect(screen.getByLabelText("Nur in der Software")).toBeDisabled());
    expect(screen.getByLabelText("Software und E-Mail")).toBeDisabled();

    resolveFetch!(
      new Response(JSON.stringify({ ...account, notificationPreference: "both" }), {
        status: 200,
      }),
    );

    await waitFor(() =>
      expect(screen.getByLabelText("Nur in der Software")).not.toBeDisabled(),
    );
  });

  it("shows an error message when saving fails", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "something went wrong" }), { status: 500 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={account} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByLabelText("Software und E-Mail"));

    await waitFor(() =>
      expect(
        screen.getByText("Einstellung konnte nicht gespeichert werden. Bitte versuche es erneut."),
      ).toBeInTheDocument(),
    );
  });
});
