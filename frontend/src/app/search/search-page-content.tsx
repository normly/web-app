// frontend/src/app/search/search-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/pagination";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useTranslation } from "@/lib/i18n/provider";
import { useJurisdiction } from "@/lib/jurisdiction/provider";

interface DesignationSummary {
  designation: string;
  is_primary: boolean;
}

interface DocumentSummary {
  id: string;
  origin_issuer: string;
  origin_number: string;
  designations: DesignationSummary[];
}

interface WorkSearchResult {
  work_id: string;
  best_match: DocumentSummary;
  other_editions_count: number;
}

interface SearchResponse {
  results: WorkSearchResult[];
  total: number;
}

const PAGE_SIZE = 20;

export function SearchPageContent() {
  const { t } = useTranslation();
  const { jurisdiction } = useJurisdiction();
  const [q, setQ] = React.useState("");
  const [issuer, setIssuer] = React.useState("");
  const [offset, setOffset] = React.useState(0);
  const [response, setResponse] = React.useState<SearchResponse | null>(null);
  const [isRateLimited, setIsRateLimited] = React.useState(false);

  const runSearch = React.useCallback(
    async (nextOffset: number) => {
      const params = new URLSearchParams({
        jurisdiction, limit: String(PAGE_SIZE), offset: String(nextOffset),
      });
      if (q) params.set("q", q);
      if (issuer) params.set("issuer", issuer);

      const result = await fetch(`/api/documents/search?${params.toString()}`);
      if (result.status === 429) {
        setIsRateLimited(true);
        return;
      }
      setIsRateLimited(false);
      setResponse(await result.json());
      setOffset(nextOffset);
    },
    [jurisdiction, q, issuer],
  );

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    runSearch(0);
  };

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={submit} className="flex gap-2">
        <Input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder={t("search.inputPlaceholder")}
          aria-label={t("search.inputPlaceholder")}
        />
        <Input
          value={issuer}
          onChange={(event) => setIssuer(event.target.value)}
          placeholder={t("search.issuerFilterLabel")}
          aria-label={t("search.issuerFilterLabel")}
          className="max-w-[10rem]"
        />
        <Button type="submit">{t("search.searchButton")}</Button>
      </form>

      {isRateLimited && <p className="text-sm text-red-600">{t("search.rateLimited")}</p>}

      {response !== null && !isRateLimited && response.results.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("search.empty")}</p>
      )}

      {response !== null && response.results.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("search.issuerColumnHeading")}</TableHead>
                <TableHead>{t("search.designationColumnHeading")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {response.results.map(({ work_id, best_match, other_editions_count }) => {
                const primary =
                  best_match.designations.find((d) => d.is_primary) ?? best_match.designations[0];
                return (
                  <TableRow key={work_id}>
                    <TableCell>{best_match.origin_issuer}</TableCell>
                    <TableCell>
                      <Link href={`/documents/${best_match.id}`} className="underline">
                        {primary?.designation ?? `${best_match.origin_issuer} ${best_match.origin_number}`}
                      </Link>
                      {other_editions_count > 0 && (
                        <span className="ml-2 text-sm text-muted-foreground">
                          +{other_editions_count} {t("search.otherEditions")}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          <Pagination
            offset={offset}
            limit={PAGE_SIZE}
            total={response.total}
            onPageChange={runSearch}
            previousLabel={t("search.previousPage")}
            nextLabel={t("search.nextPage")}
          />
        </>
      )}
    </div>
  );
}
