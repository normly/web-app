// frontend/src/components/admin/row-actions.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { AdminUserRow } from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n/provider";
import { interpolate } from "@/lib/i18n/interpolate";

export function RowActions({
  row, isSelf, onOpen, onResend, onWithdraw, onUnblock,
}: {
  row: AdminUserRow;
  isSelf: boolean;
  onOpen: (kind: "edit" | "block" | "remove") => void;
  onResend: () => void;
  onWithdraw: () => void;
  onUnblock: () => void;
}) {
  const { t } = useTranslation();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="icon" className="size-9"
                aria-label={interpolate(t("admin.actions.menu"), { email: row.email })}>
          <MoreHorizontal />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {row.kind === "invitation" ? (
          <>
            <DropdownMenuItem onSelect={onResend}>{t("admin.actions.resend")}</DropdownMenuItem>
            <DropdownMenuItem onSelect={onWithdraw} className="text-destructive">
              {t("admin.actions.withdraw")}
            </DropdownMenuItem>
          </>
        ) : (
          <>
            <DropdownMenuItem onSelect={() => onOpen("edit")} disabled={isSelf}>
              {t("admin.actions.edit")}
            </DropdownMenuItem>
            {row.status === "blocked" ? (
              <DropdownMenuItem onSelect={onUnblock} disabled={isSelf}>
                {t("admin.actions.unblock")}
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem onSelect={() => onOpen("block")} disabled={isSelf}>
                {t("admin.actions.block")}
              </DropdownMenuItem>
            )}
            <DropdownMenuItem onSelect={() => onOpen("remove")} disabled={isSelf}
                              className="text-destructive">
              {t("admin.actions.remove")}
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
