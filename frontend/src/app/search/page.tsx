// frontend/src/app/search/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { SearchPageContent } from "./search-page-content";

export default function SearchPage() {
  const config = getInstanceConfig();
  return (
    <AppShell instanceName={config.instanceName} logoPath={config.logoPath}>
      <PageHeader titleKey="nav.search" />
      <div className="mx-auto max-w-2xl p-4">
        <SearchPageContent />
      </div>
    </AppShell>
  );
}
