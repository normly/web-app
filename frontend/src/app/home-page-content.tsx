// frontend/src/app/home-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors
//
// Split out of page.tsx because page.tsx now needs to be a Server
// Component (it calls getInstanceConfig(), which reads process.env and
// is only meaningful server-side -- see AppHeader's comment) so it can
// pass instanceName/logoPath down as props, while the chat state/hooks
// below need a client component.

"use client";

import * as React from "react";
import { MessageList } from "@/components/chat/message-list";
import { ChatInput } from "@/components/chat/chat-input";
import { ChatShell } from "@/components/chat/chat-shell";
import { useTranslation } from "@/lib/i18n/provider";
import { useJurisdiction } from "@/lib/jurisdiction/provider";
import {
  assistantMessageView,
  messageViews,
  type ApiChatMessage,
  type ApiCitation,
  type ChatMessageView,
} from "@/lib/chat-answer";

interface ChatApiResponse {
  session_id: string | null;
  answer: string;
  answer_type: "structural" | "synthesis" | "fallback";
  paragraphs: string[];
  citations: ApiCitation[];
}

interface SessionMessagesResponse {
  session_id: string;
  title: string | null;
  messages: ApiChatMessage[];
}

export function HomePageContent() {
  const { t, locale } = useTranslation();
  const { jurisdiction } = useJurisdiction();
  const [messages, setMessages] = React.useState<ChatMessageView[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [activeSessionId, setActiveSessionId] = React.useState<string | null>(null);
  // Bumped whenever the sidebar's session list may have changed.
  const [sessionsVersion, setSessionsVersion] = React.useState(0);
  const refreshSessions = () => setSessionsVersion((version) => version + 1);

  const showSession = (body: SessionMessagesResponse) => {
    setActiveSessionId(body.session_id);
    setMessages(messageViews(body.messages));
  };

  // After a reload the chat cookie still names a session; show it instead of
  // an empty chat that new questions would silently continue.
  React.useEffect(() => {
    let cancelled = false;
    fetch("/api/chat/current")
      .then(async (response) => {
        if (cancelled || response.status !== 200) return;
        showSession(await response.json());
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openSession = async (sessionId: string) => {
    const response = await fetch(`/api/chat/sessions/${sessionId}/messages`);
    if (!response.ok) return;
    showSession(await response.json());
  };

  const startNewChat = () => {
    setMessages([]);
    setActiveSessionId(null);
  };

  const handleSessionsDeleted = async (deletedId: string | null) => {
    if (activeSessionId === null) return;
    if (deletedId !== null && deletedId !== activeSessionId) return;
    await fetch("/api/chat/new-session", { method: "POST" });
    startNewChat();
  };

  const sendMessage = async (message: string) => {
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setIsLoading(true);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ jurisdiction, language: locale, message }),
      });
      const body: ChatApiResponse = await response.json();
      setMessages((prev) => [...prev, assistantMessageView(body.answer, body.paragraphs, body.citations)]);
      if (body.session_id) {
        const isNewSession = activeSessionId === null;
        setActiveSessionId(body.session_id);
        refreshSessions();
        if (isNewSession) {
          // Not awaited: the title is a convenience and must never delay
          // the answer. The endpoint is idempotent.
          fetch(`/api/chat/sessions/${body.session_id}/title`, { method: "POST" })
            .then((titleResponse) => {
              if (titleResponse.ok) refreshSessions();
            })
            .catch(() => {});
        }
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <ChatShell
      onNewChat={startNewChat}
      activeSessionId={activeSessionId}
      onOpenSession={openSession}
      onSessionsDeleted={handleSessionsDeleted}
      sessionsVersion={sessionsVersion}
    >
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 p-4">
        <MessageList messages={messages} isLoading={isLoading} />
        <ChatInput onSend={sendMessage} disabled={isLoading} />
        <p className="text-center text-xs text-muted-foreground">{t("chat.aiDisclaimer")}</p>
      </div>
    </ChatShell>
  );
}
