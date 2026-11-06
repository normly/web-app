// frontend/tests/unit/profile-overlay.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ProfileOverlay } from "@/components/account/profile-overlay";
import type { AccountSummary } from "@/lib/account-response";

const originalFetch = global.fetch;

const ACCOUNT: AccountSummary = {
  accountId: "acc-1",
  email: "a@example.de",
  firstName: null,
  lastName: null,
  hasAvatar: false,
  hasPassword: true,
  notificationPreference: "immediate",
  role: "user", publisherId: null,
};

function renderOverlay(account: AccountSummary | null, open = true) {
  return render(
    <LocaleProvider initialLocale="de">
      <ProfileOverlay
        open={open} onOpenChange={vi.fn()} account={account} setAccount={vi.fn()}
        avatarVersion={0} onAvatarChange={vi.fn()}
      />
    </LocaleProvider>,
  );
}

describe("ProfileOverlay", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the login-required message when there is no account", () => {
    renderOverlay(null);
    expect(screen.getByText("Melde dich an, um dein Konto zu verwalten.")).toBeInTheDocument();
  });

  it("renders the profile section by default once an account is passed", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    renderOverlay(ACCOUNT);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Name und Profilbild" })).toBeInTheDocument(),
    );
    expect(screen.queryByRole("heading", { name: "E-Mail-Adresse" })).not.toBeInTheDocument();
  });

  it("switches to the email section when its nav item is clicked", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    renderOverlay(ACCOUNT);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Name und Profilbild" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "E-Mail-Adresse" }));
    expect(screen.getByText("Aktuelle E-Mail-Adresse", { exact: false })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Name und Profilbild" })).not.toBeInTheDocument();
  });

  it("shows the combined Konto & Daten nav item leading to both Export and Delete sections", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    renderOverlay(ACCOUNT);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Name und Profilbild" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Konto & Daten" }));
    expect(screen.getByText("Daten exportieren")).toBeInTheDocument();
    expect(screen.getByText("Konto löschen")).toBeInTheDocument();
  });

  it("marks the active nav section with aria-current", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    renderOverlay(ACCOUNT);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Name und Profilbild" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Name und Profilbild" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(screen.getByRole("button", { name: "E-Mail-Adresse" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("loads the usage when the Nutzung nav item is clicked", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(
        JSON.stringify({
          used: 1, limit: 30, resets_at: "2099-01-01T00:00:00Z",
          pool_exhausted: false, pool_resets_at: null,
        }),
        { status: 200 },
      ));
    renderOverlay(ACCOUNT);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Name und Profilbild" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Nutzung" }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith("/api/account/usage"));
  });
});
