// frontend/tests/unit/admin-row-actions.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { RowActions } from "@/components/admin/row-actions";
import { RemoveDialog } from "@/components/admin/remove-dialog";
import type { AdminUserRow } from "@/lib/admin-api";

const base: AdminUserRow = {
  kind: "account", id: "7", email: "crawler@example.de", firstName: null, lastName: null,
  signInMethods: ["email"], role: "user", publisherId: null, publisherName: null,
  lastLoginAt: null, createdAt: "2026-10-10T00:00:00Z", status: "active",
  blockReason: null, expiresAt: null,
};
const originalFetch = global.fetch;

function openMenu(row: AdminUserRow, isSelf = false) {
  render(
    <LocaleProvider initialLocale="de">
      <RowActions row={row} isSelf={isSelf} onOpen={vi.fn()} onResend={vi.fn()}
                  onWithdraw={vi.fn()} onUnblock={vi.fn()} />
    </LocaleProvider>,
  );
  fireEvent.keyDown(screen.getByRole("button", { name: `Aktionen für ${row.email}` }), { key: "Enter" });
}

describe("row actions", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("offers edit, block and remove for an active account", async () => {
    openMenu(base);
    expect(await screen.findByRole("menuitem", { name: "Bearbeiten" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Sperren" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Entfernen" })).toBeInTheDocument();
  });

  it("offers unblock for a blocked account and resend/withdraw for an invitation", async () => {
    openMenu({ ...base, status: "blocked" });
    expect(await screen.findByRole("menuitem", { name: "Entsperren" })).toBeInTheDocument();
  });

  it("offers resend and withdraw for an invitation", async () => {
    openMenu({ ...base, kind: "invitation", status: "expired" });
    expect(await screen.findByRole("menuitem", { name: "Erneut senden" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Zurückziehen" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Sperren" })).not.toBeInTheDocument();
  });

  it("disables block and remove on the own row", async () => {
    openMenu({ ...base, role: "administrator" }, true);
    expect(await screen.findByRole("menuitem", { name: "Sperren" })).toHaveAttribute("data-disabled");
    expect(screen.getByRole("menuitem", { name: "Entfernen" })).toHaveAttribute("data-disabled");
  });

  it("enables removal only after the address is typed, then calls the API", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ email_sent: true }), { status: 200 }),
    );
    const onDone = vi.fn();
    render(
      <LocaleProvider initialLocale="de">
        <RemoveDialog row={base} onClose={vi.fn()} onDone={onDone} />
      </LocaleProvider>,
    );
    const confirm = screen.getByRole("button", { name: "Endgültig entfernen" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Zur Bestätigung die E-Mail-Adresse eingeben"),
                     { target: { value: "crawler@example.de" } });
    fireEvent.click(confirm);
    await waitFor(() => expect(onDone).toHaveBeenCalledWith("Konto entfernt."));
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/admin/accounts/7");
    expect(init.method).toBe("DELETE");
  });

  it("shows the backend error code as text", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "last_administrator" }), { status: 409 }),
    );
    render(
      <LocaleProvider initialLocale="de">
        <RemoveDialog row={{ ...base, role: "administrator" }} onClose={vi.fn()} onDone={vi.fn()} />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("Zur Bestätigung die E-Mail-Adresse eingeben"),
                     { target: { value: "crawler@example.de" } });
    fireEvent.click(screen.getByRole("button", { name: "Endgültig entfernen" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Der letzte Administrator kann nicht herabgestuft, gesperrt oder entfernt werden.",
    );
  });
});
