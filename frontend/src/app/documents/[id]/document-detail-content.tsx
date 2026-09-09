// frontend/src/app/documents/[id]/document-detail-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import Link from "next/link";
import { Heart } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useTranslation } from "@/lib/i18n/provider";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";
import { useJurisdiction } from "@/lib/jurisdiction/provider";
import { useAccountSession } from "@/lib/use-account-session";

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

interface WorkStructureEntry {
  document_id: string;
  origin_issuer: string;
  origin_number: string;
  edition: string;
  designation: string | null;
  status: "valid" | "replaced" | "withdrawn";
}

interface WorkStructure {
  work_id: string;
  editions: WorkStructureEntry[];
  national_adoptions: WorkStructureEntry[];
}

interface RightsClassification {
  jurisdiction: string;
  may_process: boolean;
  may_index_fulltext: boolean;
  may_cite_passages: boolean;
  may_export_free: boolean;
  legal_basis_reference: string;
}

// Work-internal edge types are shown structurally via the edition-history and
// national-adoptions sections instead -- they must not also appear as
// generic References-list badges.
const WORK_INTERNAL_EDGE_TYPES = new Set(["replaces", "withdrawn_by", "adopted_from"]);

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

function entryLabel(entry: WorkStructureEntry): string {
  return entry.designation ?? `${entry.origin_issuer} ${entry.origin_number}`;
}

export function DocumentDetailContent({ documentId }: { documentId: string }) {
  const { t } = useTranslation();
  const { jurisdiction } = useJurisdiction();
  const { account } = useAccountSession();
  const [documentDetail, setDocumentDetail] = React.useState<DocumentDetail | null>(null);
  const [edges, setEdges] = React.useState<ResolvedEdge[]>([]);
  const [validity, setValidity] = React.useState<ValiditySummary | null>(null);
  const [workStructure, setWorkStructure] = React.useState<WorkStructure | null>(null);
  const [rights, setRights] = React.useState<RightsClassification | null>(null);
  const [notFound, setNotFound] = React.useState(false);
  const [isWatched, setIsWatched] = React.useState(false);
  const [isTogglingWatch, setIsTogglingWatch] = React.useState(false);
  const [watchError, setWatchError] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    const query = `?jurisdiction=${encodeURIComponent(jurisdiction)}`;

    async function load() {
      const [documentResponse, edgesResponse, validityResponse, workResponse, rightsResponse] =
        await Promise.all([
          fetch(`/api/documents/${documentId}${query}`),
          fetch(`/api/documents/${documentId}/edges${query}`),
          fetch(`/api/documents/${documentId}/validity${query}`),
          fetch(`/api/documents/${documentId}/work${query}`),
          fetch(`/api/documents/${documentId}/rights${query}`),
        ]);
      if (cancelled) return;

      if (documentResponse.status === 404) {
        setNotFound(true);
        return;
      }
      setDocumentDetail(await documentResponse.json());
      setValidity(validityResponse.ok ? await validityResponse.json() : null);
      setWorkStructure(workResponse.ok ? await workResponse.json() : null);
      setRights(rightsResponse.ok ? await rightsResponse.json() : null);

      const rawEdges: RawEdge[] = edgesResponse.ok ? await edgesResponse.json() : [];
      const referenceEdges = rawEdges.filter((edge) => !WORK_INTERNAL_EDGE_TYPES.has(edge.edge_type));
      const resolved = await Promise.all(
        referenceEdges.map(async (edge): Promise<ResolvedEdge> => {
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

  React.useEffect(() => {
    if (!account || !workStructure) {
      setIsWatched(false);
      return;
    }
    let cancelled = false;
    fetch("/api/account/watchlist")
      .then((response) => (response.ok ? response.json() : []))
      .then((entries: { workId: string }[]) => {
        if (!cancelled) {
          setIsWatched(entries.some((entry) => entry.workId === workStructure.work_id));
        }
      })
      .catch(() => {
        if (!cancelled) setIsWatched(false);
      });
    return () => {
      cancelled = true;
    };
  }, [account, workStructure]);

  const toggleWatch = async () => {
    if (!workStructure) return;
    setIsTogglingWatch(true);
    try {
      if (isWatched) {
        const response = await fetch(`/api/account/watchlist/${workStructure.work_id}`, {
          method: "DELETE",
        });
        if (response.ok) {
          setIsWatched(false);
          setWatchError(false);
        } else {
          setWatchError(true);
        }
      } else {
        const response = await fetch("/api/account/watchlist", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ workId: workStructure.work_id }),
        });
        if (response.ok) {
          setIsWatched(true);
          setWatchError(false);
        } else {
          setWatchError(true);
        }
      }
    } catch {
      setWatchError(true);
    } finally {
      setIsTogglingWatch(false);
    }
  };

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
        <Badge
          variant={validity.status === "valid" ? "default" : "outline"}
          data-testid="validity-badge"
        >
          {t(VALIDITY_KEYS[validity.status])}
        </Badge>
      )}

      {account && workStructure && (
        <div className="flex flex-col gap-1">
          <button
            type="button"
            onClick={toggleWatch}
            disabled={isTogglingWatch}
            aria-label={t(isWatched ? "documentDetail.removeFromWatchlist" : "documentDetail.addToWatchlist")}
            data-testid="watchlist-toggle"
          >
            <Heart className={isWatched ? "h-5 w-5 fill-current" : "h-5 w-5"} />
          </button>
          {watchError && (
            <p className="text-sm text-destructive">{t("documentDetail.watchlistToggleError")}</p>
          )}
        </div>
      )}

      <a
        href={documentDetail.source.retrieval_path}
        className="text-sm underline"
        target="_blank"
        rel="noopener noreferrer"
      >
        {documentDetail.source.publisher}
      </a>

      {workStructure && workStructure.editions.length > 0 && (
        <div>
          <h3 className="font-medium">{t("documentDetail.editionsHeading")}</h3>
          <ul className="flex flex-col gap-2" data-testid="edition-history-list">
            {workStructure.editions.map((entry) => (
              <li key={entry.document_id} className="flex items-center gap-2">
                <Badge variant={entry.status === "valid" ? "default" : "outline"}>
                  {t(VALIDITY_KEYS[entry.status])}
                </Badge>
                <Link href={`/documents/${entry.document_id}`} className="underline">
                  {entryLabel(entry)}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {workStructure && workStructure.national_adoptions.length > 0 && (
        <div>
          <h3 className="font-medium">{t("documentDetail.adoptionsHeading")}</h3>
          <ul className="flex flex-col gap-2" data-testid="national-adoptions-list">
            {workStructure.national_adoptions.map((entry) => (
              <li key={entry.document_id} className="flex items-center gap-2">
                <Badge variant={entry.status === "valid" ? "default" : "outline"}>
                  {t(VALIDITY_KEYS[entry.status])}
                </Badge>
                <Link href={`/documents/${entry.document_id}`} className="underline">
                  {entryLabel(entry)}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {edges.length > 0 && (
        <div>
          <h3 className="font-medium">{t("documentDetail.referencesHeading")}</h3>
          <ul className="flex flex-col gap-2" data-testid="references-list">
            {edges.map((edge) => (
              <li key={`${edge.edge_type}-${edge.to_document_id}`} className="flex items-center gap-2">
                <Badge variant="muted">{t(EDGE_TYPE_KEYS[edge.edge_type] ?? "edgeType.references")}</Badge>
                <Link href={`/documents/${edge.to_document_id}`} className="underline">
                  {edge.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {rights && (
        <div>
          <h3 className="font-medium">{t("documentDetail.rightsHeading")}</h3>
          <ul className="flex flex-col gap-1 text-sm">
            <li>{t("documentDetail.mayProcess")}: {rights.may_process ? "✓" : "✗"}</li>
            <li>{t("documentDetail.mayIndexFulltext")}: {rights.may_index_fulltext ? "✓" : "✗"}</li>
            <li>{t("documentDetail.mayCitePassages")}: {rights.may_cite_passages ? "✓" : "✗"}</li>
            <li>{t("documentDetail.mayExportFree")}: {rights.may_export_free ? "✓" : "✗"}</li>
            <li className="text-muted-foreground">{rights.legal_basis_reference}</li>
          </ul>
        </div>
      )}
    </div>
  );
}
