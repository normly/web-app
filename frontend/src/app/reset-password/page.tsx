// frontend/src/app/reset-password/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { ResetPasswordContent } from "./reset-password-content";

export default function ResetPasswordPage() {
  return (
    <AuthSplitLayout
      headingKey="auth.resetPasswordPageHeading"
      descriptionKey="auth.resetPasswordPageDescription"
    >
      <ResetPasswordContent />
    </AuthSplitLayout>
  );
}
