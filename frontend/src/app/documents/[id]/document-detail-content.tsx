// frontend/src/app/documents/[id]/document-detail-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { useTranslation } from "@/lib/i18n/provider";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";
import { useJurisdiction } from "@/lib/jurisdiction/provider";

interface DocumentDetail {
  id: string;
  origin_issuer: string;
  origin_number: string;
  designations: { designation: string; is_primary: boolean }[];
  titles: { language: string; title: string }[];
  source: { publisher: string; retrieval_path: string };
}

interface RawEdge {
  edge_type: string;
  to_document_id: string;
}

interface ResolvedEdge extends RawEdge {
  label: string;
}

interface ValiditySummary {
  status: "valid" | "replaced" | "withdrawn";
}

const EDGE_TYPE_KEYS: Record<string, TranslationKey> = {
  references: "edgeType.references",
  replaces: "edgeType.replaces",
  withdrawn_by: "edgeType.withdrawn_by",
  based_on_law: "edgeType.based_on_law",
  adopted_from: "edgeType.adopted_from",
};

const VALIDITY_KEYS: Record<string, TranslationKey> = {
  valid: "validity.valid",
  replaced: "validity.replaced",
  withdrawn: "validity.withdrawn",
};

export function DocumentDetailContent({ documentId }: { documentId: string }) {
  const { t } = useTranslation();
  const { jurisdiction } = useJurisdiction();
  const [documentDetail, setDocumentDetail] = React.useState<DocumentDetail | null>(null);
  const [edges, setEdges] = React.useState<ResolvedEdge[]>([]);
  const [validity, setValidity] = React.useState<ValiditySummary | null>(null);
  const [notFound, setNotFound] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    const query = `?jurisdiction=${encodeURIComponent(jurisdiction)}`;

    async function load() {
      const [documentResponse, edgesResponse, validityResponse] = await Promise.all([
        fetch(`/api/documents/${documentId}${query}`),
        fetch(`/api/documents/${documentId}/edges${query}`),
        fetch(`/api/documents/${documentId}/validity${query}`),
      ]);
      if (cancelled) return;

      if (documentResponse.status === 404) {
        setNotFound(true);
        return;
      }
      setDocumentDetail(await documentResponse.json());
      setValidity(validityResponse.ok ? await validityResponse.json() : null);

      const rawEdges: RawEdge[] = edgesResponse.ok ? await edgesResponse.json() : [];
      const resolved = await Promise.all(
        rawEdges.map(async (edge): Promise<ResolvedEdge> => {
          try {
            const targetResponse = await fetch(
              `/api/documents/${edge.to_document_id}${query}`,
            );
            const target = await targetResponse.json();
            const label =
              target.designations?.find((d: { is_primary: boolean }) => d.is_primary)
                ?.designation ?? edge.to_document_id;
            return { ...edge, label };
          } catch {
            return { ...edge, label: edge.to_document_id };
          }
        }),
      );
      if (!cancelled) setEdges(resolved);
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [documentId, jurisdiction]);

  if (notFound) {
    return <p>{t("search.notFound")}</p>;
  }
  if (documentDetail === null) {
    return null;
  }

  const primaryDesignation =
    documentDetail.designations.find((d) => d.is_primary)?.designation ??
    `${documentDetail.origin_issuer} ${documentDetail.origin_number}`;
  const primaryTitle = documentDetail.titles[0]?.title;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-xl font-semibold">{primaryDesignation}</h2>
        {primaryTitle && <p className="text-muted-foreground">{primaryTitle}</p>}
      </div>

      {validity && (
        <Badge variant={validity.status === "valid" ? "default" : "outline"}>
          {t(VALIDITY_KEYS[validity.status])}
        </Badge>
      )}

      <a
        href={documentDetail.source.retrieval_path}
        className="text-sm underline"
        target="_blank"
        rel="noopener noreferrer"
      >
        {documentDetail.source.publisher}
      </a>

      {edges.length > 0 && (
        <ul className="flex flex-col gap-2">
          {edges.map((edge) => (
            <li key={`${edge.edge_type}-${edge.to_document_id}`} className="flex items-center gap-2">
              <Badge variant="muted">{t(EDGE_TYPE_KEYS[edge.edge_type] ?? "edgeType.references")}</Badge>
              <Link href={`/documents/${edge.to_document_id}`} className="underline">
                {edge.label}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
