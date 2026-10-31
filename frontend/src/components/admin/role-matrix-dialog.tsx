// frontend/src/components/admin/role-matrix-dialog.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { adminApi, type RoleMatrix } from "@/lib/admin-api";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";
import { useTranslation } from "@/lib/i18n/provider";

// Built from the same definition the server checks (permissions.py), so the
// dialog cannot promise what the server does not enforce.
export function RoleMatrixDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const [matrix, setMatrix] = React.useState<RoleMatrix | null>(null);
  const [failed, setFailed] = React.useState(false);
  const label = (key: string) => t(key as TranslationKey);

  React.useEffect(() => {
    adminApi.roleMatrix().then(setMatrix).catch(() => setFailed(true));
  }, []);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogTitle>{t("admin.roleMatrix.title")}</DialogTitle>
        {failed && <p role="alert" className="text-sm text-destructive">{t("admin.loadError")}</p>}
        {matrix && (
          <div className="mt-4 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-left"><span className="sr-only">{t("admin.roleMatrix.capability")}</span></TableHead>
                  {matrix.roles.map((role) => (
                    <TableHead key={role} className="text-left">{label(`admin.roleMatrix.roles.${role}`)}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {matrix.rows.map((row) => (
                  <TableRow key={row.capability}>
                    <TableCell className="text-left text-muted-foreground">
                      {label(`admin.roleMatrix.capabilities.${row.capability}`)}
                      {row.planned && <Badge variant="muted" className="ml-2">{t("admin.roleMatrix.planned")}</Badge>}
                    </TableCell>
                    {matrix.roles.map((role) => (
                      <TableCell key={role} className="text-left">
                        {label(`admin.roleMatrix.values.${row.values[role]}`)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
