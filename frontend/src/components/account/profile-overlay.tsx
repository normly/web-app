// frontend/src/components/account/profile-overlay.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { NameAvatarSection } from "@/components/account/name-avatar-section";
import { EmailSection } from "@/components/account/email-section";
import { PasswordSection } from "@/components/account/password-section";
import { SessionsSection } from "@/components/account/sessions-section";
import { ExportSection } from "@/components/account/export-section";
import { DeleteAccountSection } from "@/components/account/delete-account-section";
import { useAccountSession } from "@/lib/use-account-session";
import { useTranslation } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

type SectionId = "profile" | "email" | "password" | "sessions" | "data";

const SECTIONS: { id: SectionId; labelKey: TranslationKey }[] = [
  { id: "profile", labelKey: "account.nameAvatarTitle" },
  { id: "email", labelKey: "account.emailTitle" },
  { id: "password", labelKey: "account.passwordTitle" },
  { id: "sessions", labelKey: "account.sessionsTitle" },
  { id: "data", labelKey: "account.dataSectionTitle" },
];

export function ProfileOverlay({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const { account, setAccount } = useAccountSession();
  const [activeSection, setActiveSection] = React.useState<SectionId>("profile");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogTitle>{t("account.pageTitle")}</DialogTitle>
        {!account ? (
          <p className="text-sm text-muted-foreground">{t("account.loginRequired")}</p>
        ) : (
          <div className="flex flex-col gap-6 sm:flex-row">
            <nav className="flex shrink-0 flex-row gap-1 overflow-x-auto sm:w-40 sm:flex-col sm:overflow-visible">
              {SECTIONS.map((section) => (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => setActiveSection(section.id)}
                  className={cn(
                    "whitespace-nowrap rounded-md px-3 py-2 text-left text-sm transition-colors",
                    activeSection === section.id
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  {t(section.labelKey)}
                </button>
              ))}
            </nav>
            <div className="max-h-[60vh] min-w-0 flex-1 overflow-y-auto">
              {activeSection === "profile" && (
                <NameAvatarSection account={account} onAccountUpdated={setAccount} />
              )}
              {activeSection === "email" && <EmailSection account={account} />}
              {activeSection === "password" && <PasswordSection />}
              {activeSection === "sessions" && <SessionsSection />}
              {activeSection === "data" && (
                <div className="flex flex-col gap-6">
                  <ExportSection />
                  <DeleteAccountSection account={account} />
                </div>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
