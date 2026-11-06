// frontend/tests/unit/invitation-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { InvitationPageContent } from "@/app/invitation/invitation-page-content";

const push = vi.fn();
let search = "token=inv-1";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(search),
}));
const originalFetch = global.fetch;

function renderPage() {
  render(<LocaleProvider initialLocale="de"><InvitationPageContent contact="kontakt@normly.example" /></LocaleProvider>);
}

describe("invitation page", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    search = "token=inv-1";
    push.mockReset();
  });

  it("does nothing until the button is clicked, then accepts and goes home", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ session_token: "s" })));
    renderPage();
    expect(global.fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Einladung annehmen" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/auth/invitation/accept");
    expect(JSON.parse(init.body)).toEqual({ token: "inv-1" });
  });

  it.each([
    [410, "invitation_invalid", /ungültig oder abgelaufen/],
    [403, "account_blocked", /Dein Konto ist gesperrt/],
    [409, "last_administrator", /letzten Administrator/],
  ])("shows the %s state", async (status, detail, text) => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail }), { status }));
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Einladung annehmen" }));
    expect(await screen.findByText(text)).toBeInTheDocument();
  });

  it("explains a link without token", () => {
    search = "";
    renderPage();
    expect(screen.getByText(/Link ist unvollständig/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Einladung annehmen" })).not.toBeInTheDocument();
  });
});
