// frontend/tests/unit/document-detail-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { JurisdictionProvider } from "@/lib/jurisdiction/provider";
import { DocumentDetailContent } from "@/app/documents/[id]/document-detail-content";

const originalFetch = global.fetch;

function renderDetail(documentId: string) {
  return render(
    <LocaleProvider initialLocale="de">
      <JurisdictionProvider initialJurisdiction="DE">
        <DocumentDetailContent documentId={documentId} />
      </JurisdictionProvider>
    </LocaleProvider>,
  );
}

const DOCUMENT_ID = "11111111-1111-1111-1111-111111111111";
const EDGE_TARGET_ID = "22222222-2222-2222-2222-222222222222";

describe("DocumentDetailContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders designation, title, validity, and a resolved edge link", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes(`/api/documents/${DOCUMENT_ID}/edges`)) {
        return Promise.resolve(
          new Response(
            JSON.stringify([{ edge_type: "references", to_document_id: EDGE_TARGET_ID }]),
            { status: 200 },
          ),
        );
      }
      if (url.includes(`/api/documents/${DOCUMENT_ID}/validity`)) {
        return Promise.resolve(
          new Response(JSON.stringify({ status: "valid" }), { status: 200 }),
        );
      }
      if (url.includes(`/api/documents/${EDGE_TARGET_ID}`)) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              designations: [{ designation: "DIN EN ISO 9001", is_primary: true }],
            }),
            { status: 200 },
          ),
        );
      }
      // GET /api/documents/{DOCUMENT_ID}
      return Promise.resolve(
        new Response(
          JSON.stringify({
            id: DOCUMENT_ID, origin_issuer: "DGUV", origin_number: "Vorschrift 1",
            designations: [{ designation: "DGUV Vorschrift 1", is_primary: true }],
            titles: [{ language: "de", title: "Grundsätze der Prävention" }],
            source: { publisher: "DGUV", retrieval_path: "https://www.dguv.de/publikationen" },
          }),
          { status: 200 },
        ),
      );
    });

    renderDetail(DOCUMENT_ID);

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "DGUV Vorschrift 1" })).toBeInTheDocument(),
    );
    expect(screen.getByText("Grundsätze der Prävention")).toBeInTheDocument();
    expect(screen.getByText("Gültig")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "DIN EN ISO 9001" })).toHaveAttribute(
        "href", `/documents/${EDGE_TARGET_ID}`,
      ),
    );
  });

  it("shows a not-found message on a 404", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 404 }));

    renderDetail(DOCUMENT_ID);

    await waitFor(() => expect(screen.getByText("Regelwerk nicht gefunden.")).toBeInTheDocument());
  });
});
