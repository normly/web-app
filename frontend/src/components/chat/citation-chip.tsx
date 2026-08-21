// frontend/src/components/chat/citation-chip.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

export interface CitationView {
  documentId: string;
  // null when resolving the citation to a real link failed -- degrade to
  // plain text rather than hiding the citation entirely (REQ-UI-003 still
  // wants a reference shown; only the clickable link is best-effort).
  href: string | null;
}

export function CitationChip({ citation }: { citation: CitationView }) {
  if (!citation.href) {
    return <span className="text-xs text-muted-foreground">Quelle</span>;
  }
  return (
    <a
      href={citation.href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-xs text-brand underline"
    >
      Quelle
    </a>
  );
}
