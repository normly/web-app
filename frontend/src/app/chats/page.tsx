// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppHeader } from "@/components/app-header";
import { ChatsPageContent } from "./chats-page-content";

export default function ChatsPage() {
  const config = getInstanceConfig();
  return (
    <>
      <AppHeader
        instanceName={config.instanceName}
        logoPath={config.logoPath}
        showHistoryLink={false}
      />
      <main className="mx-auto max-w-2xl p-4">
        <ChatsPageContent />
      </main>
    </>
  );
}
