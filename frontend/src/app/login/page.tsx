// frontend/src/app/login/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { Suspense } from "react";
import { getInstanceConfig } from "@/lib/config";
import { LoginPageContent } from "./login-page-content";

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageContent contact={getInstanceConfig().contactAddress} />
    </Suspense>
  );
}
