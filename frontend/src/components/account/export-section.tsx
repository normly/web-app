// frontend/src/components/account/export-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

export function ExportSection() {
  const { t } = useTranslation();
  const [isDownloading, setIsDownloading] = React.useState(false);

  const download = async () => {
    setIsDownloading(true);
    try {
      const response = await fetch("/api/account/export");
      if (!response.ok) return;
      const body = await response.json();
      const blob = new Blob([JSON.stringify(body, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "normly-konto-export.json";
      link.click();
      URL.revokeObjectURL(url);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{t("account.exportTitle")}</h2>
      <p className="text-sm text-muted-foreground">{t("account.exportDescription")}</p>
      <Button variant="outline" onClick={download} disabled={isDownloading} className="self-start">
        {t("account.exportButton")}
      </Button>
    </section>
  );
}
