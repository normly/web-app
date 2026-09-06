// frontend/src/app/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { HomePageContent } from "./home-page-content";

export default function HomePage() {
  const config = getInstanceConfig();
  return (
    <AppShell instanceName={config.instanceName} logoPath={config.logoPath}>
      <PageHeader titleKey="nav.chat" />
      <HomePageContent />
    </AppShell>
  );
}
