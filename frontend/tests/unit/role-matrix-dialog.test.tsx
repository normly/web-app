// frontend/tests/unit/role-matrix-dialog.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { RoleMatrixDialog } from "@/components/admin/role-matrix-dialog";

const originalFetch = global.fetch;

describe("RoleMatrixDialog", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders the server's matrix with translated labels and planned markers", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      roles: ["anonymous", "user", "publisher", "administrator"],
      rows: [
        { capability: "chats_of_others", planned: false,
          values: { anonymous: "no", user: "no", publisher: "no", administrator: "no" } },
        { capability: "usage_and_demand", planned: true,
          values: { anonymous: "no", user: "no", publisher: "aggregated_own", administrator: "all" } },
      ],
    })));
    render(<LocaleProvider initialLocale="de"><RoleMatrixDialog onClose={vi.fn()} /></LocaleProvider>);

    const table = await screen.findByRole("table");
    expect(within(table).getByRole("columnheader", { name: "Anonym" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Funktion" })).toBeInTheDocument();
    const row = within(table).getByRole("row", { name: /Nutzung und Nachfrage/ });
    expect(within(row).getByText("geplant")).toBeInTheDocument();
    expect(within(row).getByText("eigene Inhalte, aggregiert")).toBeInTheDocument();
  });
});
