// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { useTranslation } from "@/lib/i18n/provider";
import { ChatsPageContent } from "./chats-page-content";

export default function ChatsPage() {
  const { t } = useTranslation();
  return (
    <main className="mx-auto max-w-2xl p-4">
      <h1 className="mb-4 text-xl font-semibold">{t("history.title")}</h1>
      <ChatsPageContent />
    </main>
  );
}
