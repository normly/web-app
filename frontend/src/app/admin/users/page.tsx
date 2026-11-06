// frontend/src/app/admin/users/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { Suspense } from "react";
import { getInstanceConfig } from "@/lib/config";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { UserManagementContent } from "./user-management-content";

export default function UserManagementPage() {
  const config = getInstanceConfig();
  return (
    <AppShell instanceName={config.instanceName} logoPath={config.logoPath}>
      <PageHeader titleKey="nav.userManagement" />
      <div className="p-4 md:p-8">
        <Suspense fallback={null}>
          <UserManagementContent />
        </Suspense>
      </div>
    </AppShell>
  );
}
