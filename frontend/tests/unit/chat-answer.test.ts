// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import {
  assistantMessageView,
  citationHref,
  citationLabel,
  messageViews,
  type ApiCitation,
} from "@/lib/chat-answer";

const cite = (overrides: Partial<ApiCitation>): ApiCitation => ({
  document_id: "doc-1",
  segment_id: null,
  designation: "DIN EN ISO 12100",
  section: null,
  paragraph_index: null,
  ...overrides,
});

describe("assistantMessageView", () => {
  it("groups citations by paragraph, dedupes them and keeps whole-answer citations apart", () => {
    const view = assistantMessageView("A\n\nB", ["A", "B"], [
      cite({ segment_id: "s1", section: "5.4", paragraph_index: 0 }),
      cite({ segment_id: "s1", section: "5.4", paragraph_index: 0 }),
      cite({ document_id: "doc-2", designation: "DGUV Vorschrift 1", paragraph_index: 1 }),
      cite({ document_id: "doc-3", designation: "ISO 9001" }),
    ]);

    expect(view.paragraphs).toEqual([
      { text: "A", citations: [{ documentId: "doc-1", segmentId: "s1", designation: "DIN EN ISO 12100", section: "5.4" }] },
      { text: "B", citations: [{ documentId: "doc-2", segmentId: null, designation: "DGUV Vorschrift 1", section: null }] },
    ]);
    expect(view.answerCitations).toEqual([
      { documentId: "doc-3", segmentId: null, designation: "ISO 9001", section: null },
    ]);
  });
});

describe("messageViews", () => {
  it("maps user and assistant messages", () => {
    const views = messageViews([
      { role: "user", content: "Frage", paragraphs: ["Frage"], citations: [] },
      { role: "assistant", content: "Antwort", paragraphs: ["Antwort"], citations: [] },
    ]);
    expect(views[0]).toEqual({ role: "user", content: "Frage" });
    expect(views[1].paragraphs).toEqual([{ text: "Antwort", citations: [] }]);
  });
});

describe("citationHref and citationLabel", () => {
  it("links to the segment anchor when there is a segment", () => {
    const withSegment = { documentId: "d", segmentId: "s", designation: "DIN EN ISO 13849-1", section: "4.5.4" };
    expect(citationHref(withSegment)).toBe("/documents/d#segment-s");
    expect(citationLabel(withSegment)).toBe("DIN EN ISO 13849-1 · 4.5.4");
  });

  it("links to the document and shows only the designation otherwise", () => {
    const plain = { documentId: "d", segmentId: null, designation: "ISO 9001", section: null };
    expect(citationHref(plain)).toBe("/documents/d");
    expect(citationLabel(plain)).toBe("ISO 9001");
  });
});
