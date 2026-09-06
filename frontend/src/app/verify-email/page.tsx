// frontend/src/app/verify-email/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { VerifyEmailContent } from "./verify-email-content";

export default function VerifyEmailPage() {
  return (
    <AuthSplitLayout headingKey="auth.verifyEmailPageHeading">
      <VerifyEmailContent />
    </AuthSplitLayout>
  );
}
