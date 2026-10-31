// frontend/tests/unit/invite-dialog.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { act } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { InviteDialog } from "@/components/admin/invite-dialog";

const originalFetch = global.fetch;

function mockApi(check = { existing_account: false, verified: false, blocked: false, open_invitation: false }) {
  global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (url === "/api/admin/publishers" && (!init || !init.method)) {
      return Promise.resolve(new Response(JSON.stringify([{ id: "p1", name: "VDE Verlag" }])));
    }
    if (url === "/api/admin/publishers") {
      return Promise.resolve(new Response(JSON.stringify({ id: "p2", name: "DIN Media" }), { status: 201 }));
    }
    if (url.startsWith("/api/admin/invitations/check")) {
      return Promise.resolve(new Response(JSON.stringify(check)));
    }
    return Promise.resolve(new Response(JSON.stringify({ id: "i", email_sent: true }), { status: 201 }));
  });
}

function renderDialog(onDone = vi.fn()) {
  render(
    <LocaleProvider initialLocale="de">
      <InviteDialog onClose={vi.fn()} onDone={onDone} />
    </LocaleProvider>,
  );
  return onDone;
}

describe("InviteDialog", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("asks for a publisher only for the publisher role", async () => {
    mockApi();
    renderDialog();
    expect(screen.queryByLabelText("Verlagszuordnung")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Rolle"), { target: { value: "publisher" } });
    expect(await screen.findByLabelText("Verlagszuordnung")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), { target: { value: "p@vde.example" } });
    expect(screen.getByRole("button", { name: "Einladung senden" })).toBeDisabled();
  });

  it("sends role, publisher, language and message", async () => {
    mockApi();
    const onDone = renderDialog();
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), { target: { value: "p@vde.example" } });
    fireEvent.change(screen.getByLabelText("Rolle"), { target: { value: "publisher" } });
    fireEvent.change(await screen.findByLabelText("Verlagszuordnung"), { target: { value: "p1" } });
    fireEvent.change(screen.getByLabelText("Sprache der Einladung"), { target: { value: "en" } });
    fireEvent.change(screen.getByLabelText("Persönliche Nachricht (optional)"), { target: { value: "Hallo" } });
    fireEvent.click(screen.getByRole("button", { name: "Einladung senden" }));

    await waitFor(() => expect(onDone).toHaveBeenCalledWith("Einladung an p@vde.example gesendet."));
    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls
      .find(([url, init]) => url === "/api/admin/invitations" && init?.method === "POST");
    expect(JSON.parse(call![1].body)).toEqual({
      email: "p@vde.example", role: "publisher", publisher_id: "p1", locale: "en", message: "Hallo",
    });
  });

  it("warns about an unverified existing account and refuses a blocked one", async () => {
    mockApi({ existing_account: true, verified: false, blocked: false, open_invitation: false });
    renderDialog();
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), { target: { value: "x@example.de" } });
    fireEvent.blur(screen.getByLabelText("E-Mail-Adresse"));
    expect(await screen.findByText(/Das bestehende Konto ist unbestätigt/)).toBeInTheDocument();
  });

  it("ignores a check result for an address that is no longer in the field", async () => {
    let resolveCheck: (response: Response) => void = () => {};
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith("/api/admin/invitations/check")) {
        return new Promise<Response>((resolve) => { resolveCheck = resolve; });
      }
      return Promise.resolve(new Response("[]"));
    });
    renderDialog();
    const input = screen.getByLabelText("E-Mail-Adresse");
    fireEvent.change(input, { target: { value: "blocked@example.de" } });
    fireEvent.blur(input);
    fireEvent.change(input, { target: { value: "other@example.de" } });
    await act(async () => {
      resolveCheck(new Response(JSON.stringify({
        existing_account: true, verified: true, blocked: true, open_invitation: false,
      })));
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Einladung senden" })).toBeEnabled();
  });

  it("stays usable on a phone: height-limited, scrollable, with a side margin", () => {
    mockApi();
    renderDialog();
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveClass("max-h-[90vh]", "overflow-y-auto", "w-[calc(100%-2rem)]", "max-w-3xl");
    expect(dialog).not.toHaveClass("max-w-md");
  });

  it("creates a new publisher inline and selects it", async () => {
    mockApi();
    renderDialog();
    fireEvent.change(screen.getByLabelText("Rolle"), { target: { value: "publisher" } });
    fireEvent.change(await screen.findByLabelText("Verlagszuordnung"), { target: { value: "__new__" } });
    fireEvent.change(screen.getByLabelText("Name des Verlags"), { target: { value: "DIN Media" } });
    fireEvent.click(screen.getByRole("button", { name: "Anlegen" }));
    await waitFor(() => expect(screen.getByLabelText("Verlagszuordnung")).toHaveValue("p2"));
  });
});
