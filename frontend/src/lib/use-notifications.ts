// frontend/src/lib/use-notifications.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";

export interface Notification {
  id: string;
  workId: string;
  triggerType: string;
  triggerDocumentId: string | null;
  triggerJurisdiction: string | null;
  createdAt: string;
  readAt: string | null;
}

export function useNotifications() {
  const [notifications, setNotifications] = React.useState<Notification[]>([]);

  const refresh = React.useCallback(() => {
    fetch("/api/account/notifications")
      .then((response) => (response.ok ? response.json() : []))
      .then((body: Notification[]) => setNotifications(body))
      .catch(() => setNotifications([]));
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  const markRead = React.useCallback(async (id: string) => {
    try {
      await fetch(`/api/account/notifications/${id}`, { method: "PATCH" });
    } finally {
      refresh();
    }
  }, [refresh]);

  const unreadCount = notifications.filter((n) => n.readAt === null).length;

  return { notifications, unreadCount, markRead, refresh };
}
