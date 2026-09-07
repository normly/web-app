// frontend/tests/unit/document-detail-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor, within } from "@testing-library/react";
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
const WORK_ID = "33333333-3333-3333-3333-333333333333";
const REPLACED_EDITION_ID = "44444444-4444-4444-4444-444444444444";
const NATIONAL_ADOPTION_ID = "55555555-5555-5555-5555-555555555555";

function mockFetch(overrides: { work?: object; rights?: object } = {}) {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes(`/api/documents/${DOCUMENT_ID}/edges`)) {
      return Promise.resolve(
        new Response(
          JSON.stringify([
            { edge_type: "references", to_document_id: EDGE_TARGET_ID },
            { edge_type: "replaces", to_document_id: REPLACED_EDITION_ID },
          ]),
          { status: 200 },
        ),
      );
    }
    if (url.includes(`/api/documents/${DOCUMENT_ID}/validity`)) {
      return Promise.resolve(new Response(JSON.stringify({ status: "valid" }), { status: 200 }));
    }
    if (url.includes(`/api/documents/${DOCUMENT_ID}/work`)) {
      return Promise.resolve(
        new Response(
          JSON.stringify(
            overrides.work ?? {
              work_id: WORK_ID,
              editions: [
                {
                  document_id: REPLACED_EDITION_ID, origin_issuer: "DIN",
                  origin_number: "EN ISO 9001", edition: "2015",
                  designation: "EN ISO 9001:2015", status: "replaced",
                },
                {
                  document_id: DOCUMENT_ID, origin_issuer: "DIN",
                  origin_number: "EN ISO 9001", edition: "2018",
                  designation: "EN ISO 9001:2018", status: "valid",
                },
              ],
              national_adoptions: [
                {
                  document_id: NATIONAL_ADOPTION_ID, origin_issuer: "BS",
                  origin_number: "EN ISO 9001", edition: "2018",
                  designation: "BS EN ISO 9001:2018", status: "valid",
                },
              ],
            },
          ),
          { status: 200 },
        ),
      );
    }
    if (url.includes(`/api/documents/${DOCUMENT_ID}/rights`)) {
      return Promise.resolve(
        new Response(
          JSON.stringify(
            overrides.rights ?? {
              jurisdiction: "DE", may_process: true, may_index_fulltext: true,
              may_cite_passages: true, may_export_free: false,
              legal_basis_reference: "§ 5 UrhG",
            },
          ),
          { status: 200 },
        ),
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
          id: DOCUMENT_ID, origin_issuer: "DIN", origin_number: "EN ISO 9001",
          designations: [{ designation: "EN ISO 9001:2018", is_primary: true }],
          titles: [{ language: "de", title: "Qualitätsmanagementsysteme" }],
          source: { publisher: "DIN", retrieval_path: "https://example.de" },
        }),
        { status: 200 },
      ),
    );
  });
}

describe("DocumentDetailContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders designation, title, validity, and a resolved reference link", async () => {
    mockFetch();

    renderDetail(DOCUMENT_ID);

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "EN ISO 9001:2018" })).toBeInTheDocument(),
    );
    expect(screen.getByText("Qualitätsmanagementsysteme")).toBeInTheDocument();
    // "Gültig" legitimately renders twice: the top validity badge and the
    // current edition's entry in the edition-history list share the exact
    // same status label -- assert presence, not uniqueness.
    expect(screen.getAllByText("Gültig").length).toBeGreaterThan(0);
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

  it("renders the edition history, marking the replaced edition and the current one", async () => {
    mockFetch();

    renderDetail(DOCUMENT_ID);

    await waitFor(() =>
      expect(screen.getByTestId("edition-history-list")).toBeInTheDocument(),
    );
    // Scoped to the edition-history list: the current edition's designation
    // ("EN ISO 9001:2018") also appears in the page heading, so an unscoped
    // query would find two matches.
    const editionHistory = within(screen.getByTestId("edition-history-list"));
    expect(editionHistory.getByText("EN ISO 9001:2015")).toBeInTheDocument();
    expect(editionHistory.getByText("EN ISO 9001:2018")).toBeInTheDocument();
  });

  it("renders national adoptions separately from the edition history", async () => {
    mockFetch();

    renderDetail(DOCUMENT_ID);

    await waitFor(() => expect(screen.getByText("BS EN ISO 9001:2018")).toBeInTheDocument());
  });

  it("does not show a Work-internal edge type in the references list", async () => {
    mockFetch();

    renderDetail(DOCUMENT_ID);

    await waitFor(() =>
      expect(screen.getByRole("link", { name: "DIN EN ISO 9001" })).toBeInTheDocument(),
    );
    // "replaces" is a Work-internal edge type -- it must appear only via the
    // edition-history section (asserted above), never as a References-list
    // badge for this edge type. Scoped to the references list because the
    // German label for edgeType.replaces ("Ersetzt") is identical to the
    // validity.replaced label legitimately shown on the replaced edition's
    // edition-history entry.
    const referencesList = within(screen.getByTestId("references-list"));
    expect(referencesList.queryByText("Ersetzt")).not.toBeInTheDocument();
  });

  it("renders the rights classification", async () => {
    mockFetch();

    renderDetail(DOCUMENT_ID);

    await waitFor(() => expect(screen.getByText("§ 5 UrhG")).toBeInTheDocument());
  });
});
