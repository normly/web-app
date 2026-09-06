// frontend/src/components/chat/chat-history-sidebar.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarProvider,
} from "@/components/ui/sidebar";
import { useTranslation } from "@/lib/i18n/provider";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

interface ChatSessionSummary {
  id: string;
  session_token: string;
  jurisdiction: string;
  language: string;
  created_at: string;
}

interface Bucket {
  labelKey: TranslationKey;
  sessions: ChatSessionSummary[];
}

function isSameCalendarDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function groupSessionsByBucket(sessions: ChatSessionSummary[], now: Date): Bucket[] {
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const sevenDaysAgo = new Date(now);
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const buckets: Bucket[] = [
    { labelKey: "history.bucketToday", sessions: [] },
    { labelKey: "history.bucketYesterday", sessions: [] },
    { labelKey: "history.bucketLast7Days", sessions: [] },
    { labelKey: "history.bucketOlder", sessions: [] },
  ];

  const sorted = [...sessions].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  for (const session of sorted) {
    const createdAt = new Date(session.created_at);
    if (isSameCalendarDay(createdAt, now)) {
      buckets[0].sessions.push(session);
    } else if (isSameCalendarDay(createdAt, yesterday)) {
      buckets[1].sessions.push(session);
    } else if (createdAt.getTime() >= sevenDaysAgo.getTime()) {
      buckets[2].sessions.push(session);
    } else {
      buckets[3].sessions.push(session);
    }
  }
  return buckets.filter((bucket) => bucket.sessions.length > 0);
}

export function ChatHistorySidebar({ onNewChat }: { onNewChat: () => void }) {
  const { t, locale } = useTranslation();
  const [sessions, setSessions] = React.useState<ChatSessionSummary[] | null>(null);
  const [requiresLogin, setRequiresLogin] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    fetch("/api/chat/sessions").then(async (response) => {
      if (cancelled) return;
      if (response.status === 401) {
        setRequiresLogin(true);
        return;
      }
      setSessions(await response.json());
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleNewChat = async () => {
    await fetch("/api/chat/new-session", { method: "POST" });
    onNewChat();
  };

  const buckets = sessions ? groupSessionsByBucket(sessions, new Date()) : [];

  return (
    // collapsible="offcanvas" (the default): hidden entirely behind a
    // Sheet on mobile until its own trigger (rendered in ChatShell's
    // SidebarInset, never in here -- see Global Constraints) opens it;
    // visible inline on desktop by default. This SidebarProvider's own
    // sidebar_state cookie write collides with AppShell's outer one --
    // accepted, see Global Constraints, not fixed here.
    <SidebarProvider>
      <Sidebar>
        <SidebarHeader className="p-2">
          <Button onClick={handleNewChat} variant="outline" className="w-full justify-start gap-2">
            <Plus className="size-4" />
            {t("history.newChatButton")}
          </Button>
        </SidebarHeader>
        <SidebarContent>
          {requiresLogin && (
            <p className="p-2 text-sm text-muted-foreground">{t("history.loginRequired")}</p>
          )}
          {sessions !== null && sessions.length === 0 && (
            <p className="p-2 text-sm text-muted-foreground">{t("history.empty")}</p>
          )}
          {buckets.map((bucket) => (
            <SidebarGroup key={bucket.labelKey}>
              <SidebarGroupLabel>{t(bucket.labelKey)}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {bucket.sessions.map((session) => (
                    <SidebarMenuItem key={session.id}>
                      {/* Plain text, not a link or button: no session-
                          resumption feature exists (see Global Constraints)
                          -- this must not look clickable. */}
                      <span className="flex h-8 items-center rounded-md px-2 text-sm text-sidebar-foreground/70">
                        {new Date(session.created_at).toLocaleString(locale)}
                      </span>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
        </SidebarContent>
      </Sidebar>
    </SidebarProvider>
  );
}
