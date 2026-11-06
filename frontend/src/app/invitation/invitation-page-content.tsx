// frontend/src/app/invitation/invitation-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { BlockedNotice } from "@/components/auth/blocked-notice";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

type State = "ready" | "accepting" | "invalid" | "blocked" | "lastAdministrator" | "error";

// Unlike the magic link, nothing happens on load: accepting binds a role, so
// it needs a deliberate click, and link scanners cannot use up the token.
export function InvitationPageContent({ contact }: { contact: string | null }) {
  const { t } = useTranslation();
  const router = useRouter();
  const token = useSearchParams().get("token");
  const [state, setState] = React.useState<State>("ready");

  async function accept() {
    setState("accepting");
    try {
      const response = await fetch("/api/auth/invitation/accept", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (response.ok) {
        router.push("/");
        return;
      }
      const body = await response.json().catch(() => ({}));
      setState(
        body.detail === "account_blocked" ? "blocked"
          : body.detail === "last_administrator" ? "lastAdministrator"
            : response.status === 410 ? "invalid" : "error",
      );
    } catch {
      setState("error");
    }
  }

  return (
    <AuthSplitLayout headingKey="invitation.heading" descriptionKey={token ? "invitation.description" : undefined}>
      {!token && <p className="text-sm">{t("invitation.missingToken")}</p>}
      {token && (state === "ready" || state === "accepting") && (
        <Button onClick={accept} disabled={state === "accepting"}>
          {state === "accepting" ? t("invitation.accepting") : t("invitation.accept")}
        </Button>
      )}
      {state === "invalid" && <p role="alert" className="text-sm text-destructive">{t("invitation.invalid")}</p>}
      {state === "blocked" && <BlockedNotice contact={contact} />}
      {state === "lastAdministrator" && (
        <p role="alert" className="text-sm text-destructive">{t("invitation.lastAdministrator")}</p>
      )}
      {state === "error" && <p role="alert" className="text-sm text-destructive">{t("admin.errors.generic")}</p>}
    </AuthSplitLayout>
  );
}
