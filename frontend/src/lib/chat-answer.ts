// frontend/src/lib/chat-answer.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

// Turns chat/'s answer format (paragraphs + citations with a paragraph
// index) into what MessageList renders. Shared by fresh answers and
// reopened sessions, so both look the same.

export interface ApiCitation {
  document_id: string;
  segment_id: string | null;
  designation: string;
  section: string | null;
  // null: the citation backs the whole answer, not one paragraph.
  paragraph_index: number | null;
}

export interface ApiChatMessage {
  role: "user" | "assistant";
  content: string;
  paragraphs: string[];
  citations: ApiCitation[];
}

export interface CitationView {
  documentId: string;
  segmentId: string | null;
  designation: string;
  section: string | null;
}

export interface AnswerParagraph {
  text: string;
  citations: CitationView[];
}

export interface ChatMessageView {
  role: "user" | "assistant";
  content: string;
  paragraphs?: AnswerParagraph[];
  answerCitations?: CitationView[];
}

function toView(citation: ApiCitation): CitationView {
  return {
    documentId: citation.document_id,
    segmentId: citation.segment_id,
    designation: citation.designation,
    section: citation.section,
  };
}

function dedupe(citations: CitationView[]): CitationView[] {
  const seen = new Set<string>();
  return citations.filter((citation) => {
    const key = `${citation.documentId}:${citation.segmentId ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function assistantMessageView(
  content: string,
  paragraphs: string[],
  citations: ApiCitation[],
): ChatMessageView {
  return {
    role: "assistant",
    content,
    paragraphs: paragraphs.map((text, index) => ({
      text,
      citations: dedupe(citations.filter((c) => c.paragraph_index === index).map(toView)),
    })),
    answerCitations: dedupe(citations.filter((c) => c.paragraph_index === null).map(toView)),
  };
}

export function messageViews(messages: ApiChatMessage[]): ChatMessageView[] {
  return messages.map((message) =>
    message.role === "user"
      ? { role: "user", content: message.content }
      : assistantMessageView(message.content, message.paragraphs, message.citations),
  );
}

export function citationHref(citation: CitationView): string {
  return citation.segmentId
    ? `/documents/${citation.documentId}#segment-${citation.segmentId}`
    : `/documents/${citation.documentId}`;
}

export function citationLabel(citation: CitationView): string {
  return citation.section ? `${citation.designation} · ${citation.section}` : citation.designation;
}
