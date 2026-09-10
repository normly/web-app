// frontend/src/app/documents/[id]/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { DocumentDetailContent } from "./document-detail-content";

export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const config = getInstanceConfig();
  return (
    <AppShell instanceName={config.instanceName} logoPath={config.logoPath}>
      <PageHeader titleKey="nav.documentDetailTitle" />
      <div className="mx-auto max-w-5xl p-4">
        <DocumentDetailContent documentId={id} />
      </div>
    </AppShell>
  );
}
