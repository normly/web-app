// frontend/src/app/invitation/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { Suspense } from "react";
import { getInstanceConfig } from "@/lib/config";
import { InvitationPageContent } from "./invitation-page-content";

export default function InvitationPage() {
  return (
    <Suspense fallback={null}>
      <InvitationPageContent contact={getInstanceConfig().contactAddress} />
    </Suspense>
  );
}
