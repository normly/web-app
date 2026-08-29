// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { Button } from "@/components/ui/button";

export function Pagination({
  offset,
  limit,
  total,
  onPageChange,
  previousLabel,
  nextLabel,
}: {
  offset: number;
  limit: number;
  total: number;
  onPageChange: (nextOffset: number) => void;
  previousLabel: string;
  nextLabel: string;
}) {
  const hasPrevious = offset > 0;
  const hasNext = offset + limit < total;
  return (
    <div className="flex items-center justify-between gap-2">
      <Button
        variant="outline"
        size="sm"
        disabled={!hasPrevious}
        onClick={() => onPageChange(Math.max(0, offset - limit))}
      >
        {previousLabel}
      </Button>
      <span className="text-sm text-muted-foreground">
        {total === 0 ? 0 : offset + 1}–{Math.min(offset + limit, total)} / {total}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={!hasNext}
        onClick={() => onPageChange(offset + limit)}
      >
        {nextLabel}
      </Button>
    </div>
  );
}
