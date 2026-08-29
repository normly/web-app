// frontend/src/app/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppHeader } from "@/components/app-header";
import { HomePageContent } from "./home-page-content";

export default function HomePage() {
  const config = getInstanceConfig();
  return (
    <>
      <AppHeader instanceName={config.instanceName} logoPath={config.logoPath} />
      <HomePageContent />
    </>
  );
}
