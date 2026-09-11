// frontend/tests/unit/notification-preference-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { NotificationPreferenceSection } from "@/components/account/notification-preference-section";
import type { AccountSummary } from "@/lib/account-response";

const originalFetch = global.fetch;

function makeAccount(notificationPreference: string): AccountSummary {
  return {
    accountId: "acc-1", email: "a@example.de", firstName: null, lastName: null,
    hasAvatar: false, hasPassword: true, notificationPreference,
  };
}

describe("NotificationPreferenceSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows both switches off when the preference is none", () => {
    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("none")} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    expect(screen.getByLabelText("In der Software")).not.toBeChecked();
    expect(screen.getByLabelText("Per E-Mail")).not.toBeChecked();
  });

  it("shows only the in-app switch on when the preference is in_app", () => {
    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("in_app")} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    expect(screen.getByLabelText("In der Software")).toBeChecked();
    expect(screen.getByLabelText("Per E-Mail")).not.toBeChecked();
  });

  it("shows only the email switch on when the preference is email", () => {
    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("email")} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    expect(screen.getByLabelText("In der Software")).not.toBeChecked();
    expect(screen.getByLabelText("Per E-Mail")).toBeChecked();
  });

  it("shows both switches on when the preference is both", () => {
    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("both")} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    expect(screen.getByLabelText("In der Software")).toBeChecked();
    expect(screen.getByLabelText("Per E-Mail")).toBeChecked();
  });

  it("turning the email switch on from in_app computes both", async () => {
    const onAccountUpdated = vi.fn();
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(makeAccount("both")), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("in_app")} onAccountUpdated={onAccountUpdated} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByLabelText("Per E-Mail"));

    await waitFor(() => expect(onAccountUpdated).toHaveBeenCalled());
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ notification_preference: "both" });
  });

  it("turning the in-app switch off from both computes email", async () => {
    const onAccountUpdated = vi.fn();
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(makeAccount("email")), { status: 200 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("both")} onAccountUpdated={onAccountUpdated} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByLabelText("In der Software"));

    await waitFor(() => expect(onAccountUpdated).toHaveBeenCalled());
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ notification_preference: "email" });
  });

  it("disables both switches while a save is in flight", async () => {
    let resolveFetch: ((response: Response) => void) | undefined;
    global.fetch = vi.fn().mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("none")} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByLabelText("In der Software"));

    await waitFor(() => expect(screen.getByLabelText("In der Software")).toBeDisabled());
    expect(screen.getByLabelText("Per E-Mail")).toBeDisabled();

    resolveFetch!(new Response(JSON.stringify(makeAccount("in_app")), { status: 200 }));

    await waitFor(() => expect(screen.getByLabelText("In der Software")).not.toBeDisabled());
  });

  it("reverts to the account's own state and shows an error when saving fails", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "something went wrong" }), { status: 500 }),
    );

    render(
      <LocaleProvider initialLocale="de">
        <NotificationPreferenceSection account={makeAccount("none")} onAccountUpdated={vi.fn()} />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByLabelText("In der Software"));

    await waitFor(() =>
      expect(
        screen.getByText("Einstellung konnte nicht gespeichert werden. Bitte versuche es erneut."),
      ).toBeInTheDocument(),
    );
    // account.notificationPreference is still "none" (the prop never changed,
    // since onAccountUpdated is only called on a successful response) -- the
    // switch must reflect that, not stay optimistically "on".
    expect(screen.getByLabelText("In der Software")).not.toBeChecked();
  });
});
