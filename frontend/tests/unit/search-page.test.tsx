// frontend/tests/unit/search-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { JurisdictionProvider } from "@/lib/jurisdiction/provider";
import { SearchPageContent } from "@/app/search/search-page-content";

const originalFetch = global.fetch;

function renderPage() {
  return render(
    <LocaleProvider initialLocale="de">
      <JurisdictionProvider initialJurisdiction="DE">
        <SearchPageContent />
      </JurisdictionProvider>
    </LocaleProvider>,
  );
}

describe("SearchPageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("submits the query and renders a result as a link to its detail page", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          results: [
            {
              work_id: "22222222-2222-2222-2222-222222222222",
              best_match: {
                id: "11111111-1111-1111-1111-111111111111",
                origin_issuer: "DGUV", origin_number: "Vorschrift 1",
                designations: [{ designation: "DGUV Vorschrift 1", is_primary: true }],
              },
              other_editions_count: 0,
            },
          ],
          total: 1,
        }),
        { status: 200 },
      ),
    );

    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Regelwerk suchen…"), {
      target: { value: "Vorschrift" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Suchen" }));

    await waitFor(() =>
      expect(screen.getByRole("link", { name: "DGUV Vorschrift 1" })).toHaveAttribute(
        "href", "/documents/11111111-1111-1111-1111-111111111111",
      ),
    );
  });

  it("renders results as a table with issuer and designation columns", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          results: [
            {
              work_id: "22222222-2222-2222-2222-222222222222",
              best_match: {
                id: "11111111-1111-1111-1111-111111111111",
                origin_issuer: "DGUV", origin_number: "Vorschrift 1",
                designations: [{ designation: "DGUV Vorschrift 1", is_primary: true }],
              },
              other_editions_count: 0,
            },
          ],
          total: 1,
        }),
        { status: 200 },
      ),
    );

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Suchen" }));

    await waitFor(() => expect(screen.getByRole("table")).toBeInTheDocument());
    expect(screen.getByRole("columnheader", { name: "Herausgeber" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Bezeichnung" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "DGUV" })).toBeInTheDocument();
  });

  it("shows an other-editions count when a Work has more than one matching edition", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          results: [
            {
              work_id: "22222222-2222-2222-2222-222222222222",
              best_match: {
                id: "11111111-1111-1111-1111-111111111111",
                origin_issuer: "DIN", origin_number: "EN ISO 9001",
                designations: [{ designation: "EN ISO 9001:2018", is_primary: true }],
              },
              other_editions_count: 2,
            },
          ],
          total: 1,
        }),
        { status: 200 },
      ),
    );

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Suchen" }));

    await waitFor(() => expect(screen.getByText("+2 weitere Ausgabe(n)")).toBeInTheDocument());
  });

  it("shows an empty state when there are no results", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ results: [], total: 0 }), { status: 200 }),
    );

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Suchen" }));

    await waitFor(() => expect(screen.getByText("Keine Treffer.")).toBeInTheDocument());
  });

  it("shows a rate-limit message on a 429 without crashing", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "rate limit exceeded" }), { status: 429 }),
    );

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Suchen" }));

    await waitFor(() =>
      expect(
        screen.getByText("Zu viele Anfragen. Bitte melde dich an oder versuche es später erneut."),
      ).toBeInTheDocument(),
    );
  });
});
