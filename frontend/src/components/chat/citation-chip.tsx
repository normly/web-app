// frontend/src/components/chat/citation-chip.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import Link from "next/link";
import { FileText } from "lucide-react";
import { citationHref, citationLabel, type CitationView } from "@/lib/chat-answer";

export type { CitationView };

// Names the norm and section, so the reader sees where an answer stands
// without opening anything; the link opens the passage on the document page
// (REQ-UI-003).
export function CitationChip({ citation }: { citation: CitationView }) {
  return (
    <Link
      href={citationHref(citation)}
      className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs text-foreground hover:bg-muted"
    >
      <FileText className="size-3 text-muted-foreground" aria-hidden="true" />
      {citationLabel(citation)}
    </Link>
  );
}
