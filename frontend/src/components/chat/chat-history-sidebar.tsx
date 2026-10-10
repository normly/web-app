// frontend/src/components/chat/chat-history-sidebar.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
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

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

// Whole calendar days between `now` and `createdAt` (0 = same day, 1 = the
// day before, etc.), computed from local-midnight-normalized dates so the
// "Vor 7 Tagen"/"Älter" cutoff uses the same calendar-day model as
// "Heute"/"Gestern" -- not a rolling 24h*7 window, which would put a
// morning session from exactly 7 days ago in a different bucket than an
// evening session from the same calendar date, depending on what time of
// day `now` happens to be.
function calendarDaysAgo(now: Date, createdAt: Date): number {
  const msPerDay = 24 * 60 * 60 * 1000;
  return Math.round((startOfDay(now).getTime() - startOfDay(createdAt).getTime()) / msPerDay);
}

function groupSessionsByBucket(sessions: ChatSessionSummary[], now: Date): Bucket[] {
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
    const daysAgo = calendarDaysAgo(now, createdAt);
    if (daysAgo === 0) {
      buckets[0].sessions.push(session);
    } else if (daysAgo === 1) {
      buckets[1].sessions.push(session);
    } else if (daysAgo <= 7) {
      buckets[2].sessions.push(session);
    } else {
      buckets[3].sessions.push(session);
    }
  }
  return buckets.filter((bucket) => bucket.sessions.length > 0);
}

// What the open confirmation dialog is about; null = dialog closed.
type DeleteTarget = { kind: "one"; id: string } | { kind: "all" } | null;

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

  const [deleteTarget, setDeleteTarget] = React.useState<DeleteTarget>(null);
  const [deleteFailed, setDeleteFailed] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);

  const openDeleteDialog = (target: DeleteTarget) => {
    setDeleteFailed(false);
    setDeleteTarget(target);
  };

  const confirmDelete = async () => {
    if (deleteTarget === null) return;
    const target = deleteTarget;
    setIsDeleting(true);
    try {
      const url = target.kind === "one" ? `/api/chat/sessions/${target.id}` : "/api/chat/sessions";
      const response = await fetch(url, { method: "DELETE" });
      if (!response.ok) {
        setDeleteFailed(true);
        return;
      }
      setSessions((current) =>
        current === null ? current : target.kind === "all" ? [] : current.filter((s) => s.id !== target.id),
      );
      setDeleteTarget(null);
    } catch {
      setDeleteFailed(true);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleNewChat = async () => {
    await fetch("/api/chat/new-session", { method: "POST" });
    onNewChat();
  };

  const buckets = sessions ? groupSessionsByBucket(sessions, new Date()) : [];

  return (
    // No SidebarProvider here: this component is always rendered as a
    // sibling of SidebarInset/SidebarTrigger under ChatShell's own
    // SidebarProvider (Task 5), matching the only existing precedent in
    // this codebase, app-shell.tsx -- one provider shared by Sidebar and
    // SidebarInset as siblings, never nested inside either. useSidebar()
    // resolves to the nearest ancestor provider, so an internal provider
    // here would disconnect ChatShell's mobile SidebarTrigger from this
    // Sidebar's state. collapsible="offcanvas" (the default): hidden
    // entirely behind a Sheet on mobile until that shared trigger opens
    // it; visible inline on desktop by default.
    //
    // Known limitation, documented not fixed (accepted for this plan):
    // the chat page still nests ChatShell's SidebarProvider inside
    // AppShell's own outer one (page.tsx), so there are two independent
    // SidebarProvider instances on the page even though this component
    // itself adds none. The vendored sidebar.tsx primitive assumes at
    // most one provider per page and shows two symptoms as a result:
    // (1) both providers read/write the same `sidebar_state` cookie
    // (SIDEBAR_COOKIE_NAME in sidebar.tsx), so one provider's persisted
    // open/collapsed state silently clobbers the other's; (2) both
    // providers independently attach a window-level Ctrl/Cmd+B keydown
    // listener (also in sidebar.tsx), so a single keypress toggles both
    // sidebars at once, and the inner sidebar's off-canvas position ends
    // up misaligned relative to the outer one's new (collapsed) width --
    // visible as clipped/overlapping content at the boundary. Both share
    // the same root cause (sidebar.tsx being written for a single
    // provider) and the same resolution path: whoever eventually forks
    // sidebar.tsx to support multiple independent providers per page
    // should address both together, e.g. via a per-provider cookie name/
    // id and an opt-out for the global keyboard shortcut. Out of scope
    // for this plan.
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
                    <div className="flex h-8 items-center justify-between gap-1">
                      <span className="rounded-md px-2 text-sm text-sidebar-foreground/70">
                        {new Date(session.created_at).toLocaleString(locale)}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7"
                        aria-label={t("history.deleteButton")}
                        onClick={() => openDeleteDialog({ kind: "one", id: session.id })}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
        {sessions !== null && sessions.length > 0 && (
          <Button
            variant="ghost"
            className="m-2 justify-start gap-2 text-destructive"
            onClick={() => openDeleteDialog({ kind: "all" })}
          >
            <Trash2 className="size-4" />
            {t("history.deleteAllButton")}
          </Button>
        )}
      </SidebarContent>
      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !isDeleting) setDeleteTarget(null);
        }}
      >
        <DialogContent>
          <DialogTitle>
            {deleteTarget?.kind === "all"
              ? t("history.confirmDeleteAllTitle")
              : t("history.confirmDeleteOneTitle")}
          </DialogTitle>
          <p className="mt-2 text-sm text-muted-foreground">
            {deleteTarget?.kind === "all"
              ? t("history.confirmDeleteAllDescription")
              : t("history.confirmDeleteOneDescription")}
          </p>
          {deleteFailed && (
            <p role="alert" className="mt-2 text-sm text-destructive">
              {t("history.deleteError")}
            </p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={isDeleting}>
              {t("history.cancelButton")}
            </Button>
            <Button variant="destructive" onClick={confirmDelete} disabled={isDeleting}>
              {t("history.confirmDeleteButton")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Sidebar>
  );
}
