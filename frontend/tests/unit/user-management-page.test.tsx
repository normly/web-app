// frontend/tests/unit/user-management-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { act } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { UserManagementContent } from "@/app/admin/users/user-management-content";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => "/admin/users",
  useSearchParams: () => new URLSearchParams(search),
}));

const originalFetch = global.fetch;

const summary = {
  accounts_total: 1284, accounts_active_30_days: 412,
  accounts_by_role: { user: 1279, publisher: 3, administrator: 2 },
  publishers_with_accounts: 2, open_invitations: 1, blocked: 1,
  most_frequent_block_reason: "bulk_retrieval",
};
const row = (overrides: Record<string, unknown>) => ({
  kind: "account", id: "1", email: "ops@normly.example", first_name: "Jonas",
  last_name: "Keller", sign_in_methods: ["email"], role: "administrator",
  publisher_id: null, publisher_name: null, last_login_at: null,
  created_at: "2026-03-15T10:00:00Z", status: "active", block_reason: null, expires_at: null,
  ...overrides,
});

function mockApi(status = 200) {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.startsWith("/api/auth/session")) {
      return Promise.resolve(new Response(JSON.stringify({ account: null })));
    }
    if (status !== 200) {
      return Promise.resolve(new Response(JSON.stringify({ detail: "forbidden" }), { status }));
    }
    if (url.startsWith("/api/admin/users/summary")) {
      return Promise.resolve(new Response(JSON.stringify(summary)));
    }
    return Promise.resolve(new Response(JSON.stringify({
      rows: [
        row({}),
        row({ id: "2", kind: "invitation", email: "partner@vde.example", first_name: null,
              last_name: null, sign_in_methods: [], role: "publisher", publisher_name: "VDE Verlag",
              created_at: null, status: "invited" }),
      ],
      total: 1284, page: 1, page_size: 10,
    })));
  });
}

function renderPage() {
  return render(
    <LocaleProvider initialLocale="de"><UserManagementContent /></LocaleProvider>,
  );
}

describe("UserManagementContent", () => {
  beforeEach(() => {
    search = "";
    replace.mockReset();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the summary, the role tabs with counts and the rows", async () => {
    mockApi();
    renderPage();
    expect(await screen.findByText("1.284", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("davon 412 in den letzten 30 Tagen aktiv")).toBeInTheDocument();
    expect(screen.getByText("häufigster Grund: Massenabruf")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Publisher\s*3/ })).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).getByText("ops@normly.example")).toBeInTheDocument();
    expect(within(table).getByText("Eingeladen")).toBeInTheDocument();
    expect(within(table).getByText("VDE Verlag")).toBeInTheDocument();
    expect(screen.getByText("Zeige 1 bis 10 von 1.284 Zeilen")).toBeInTheDocument();
    expect(screen.getByText("Seite 1 von 129")).toBeInTheDocument();
  });

  it("writes sorting, filters and paging into the URL", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("table");

    fireEvent.click(screen.getByRole("button", { name: "Letzte Anmeldung" }));
    expect(replace).toHaveBeenLastCalledWith("/admin/users?sort=last_login_at", { scroll: false });

    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "blocked" } });
    expect(replace).toHaveBeenLastCalledWith("/admin/users?status=blocked", { scroll: false });

    fireEvent.click(screen.getByRole("button", { name: "Nächste Seite" }));
    expect(replace).toHaveBeenLastCalledWith("/admin/users?page=2", { scroll: false });
  });

  it("marks the sorted column with aria-sort", async () => {
    search = "sort=email&order=desc";
    mockApi();
    renderPage();
    await screen.findByRole("table");
    expect(screen.getByRole("columnheader", { name: "Konto" })).toHaveAttribute("aria-sort", "descending");
  });

  it("shows the no-access state on 403", async () => {
    mockApi(403);
    renderPage();
    expect(await screen.findByText("Kein Zugriff. Diese Seite ist Administratoren vorbehalten."))
      .toBeInTheDocument();
  });

  it("debounces the search into the URL and lets an external q change win", async () => {
    try {
      mockApi();
      const ui = () => (
        <LocaleProvider initialLocale="de"><UserManagementContent /></LocaleProvider>
      );
      const { rerender } = render(ui());
      await screen.findByRole("table");
      vi.useFakeTimers();
      const input = screen.getByRole("searchbox");
      fireEvent.change(input, { target: { value: "vde" } });
      expect(replace).not.toHaveBeenCalled();
      act(() => { vi.advanceTimersByTime(300); });
      expect(replace).toHaveBeenLastCalledWith("/admin/users?q=vde", { scroll: false });

      replace.mockReset();
      search = "q=extern";
      rerender(ui());
      expect(input).toHaveValue("extern");
      search = "";
      rerender(ui());
      expect(input).toHaveValue("");
      act(() => { vi.advanceTimersByTime(500); });
      expect(replace).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});
