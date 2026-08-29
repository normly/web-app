// frontend/src/app/documents/[id]/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppHeader } from "@/components/app-header";
import { DocumentDetailContent } from "./document-detail-content";

export default function DocumentDetailPage({ params }: { params: { id: string } }) {
  const config = getInstanceConfig();
  return (
    <>
      <AppHeader instanceName={config.instanceName} logoPath={config.logoPath} />
      <main className="mx-auto max-w-2xl p-4">
        <DocumentDetailContent documentId={params.id} />
      </main>
    </>
  );
}
