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
import { chatErrorNotice } from "@/lib/chat-error-notice";
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

  // Bumped on every view change (new chat, open session, send). Async
  // results apply only if the generation they started with is still
  // current, so late replies never mix into another session's view.
  const viewGeneration = React.useRef(0);

  const showSession = (body: SessionMessagesResponse) => {
    setActiveSessionId(body.session_id);
    setMessages(messageViews(body.messages));
  };

  // After a reload the chat cookie still names a session; show it instead of
  // an empty chat that new questions would silently continue. Applies only
  // if nothing else changed the view meanwhile (generation still 0; sending
  // a message bumps it too).
  React.useEffect(() => {
    let cancelled = false;
    fetch("/api/chat/current")
      .then(async (response) => {
        if (cancelled || response.status !== 200) return;
        const body = await response.json();
        if (cancelled || viewGeneration.current !== 0) return;
        showSession(body);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openSession = async (sessionId: string) => {
    const generation = ++viewGeneration.current;
    try {
      const response = await fetch(`/api/chat/sessions/${sessionId}/messages`);
      if (!response.ok) return;
      const body = await response.json();
      if (viewGeneration.current !== generation) return;
      showSession(body);
    } catch {
      // Leave the current view unchanged.
    }
  };

  const startNewChat = () => {
    viewGeneration.current += 1;
    setMessages([]);
    setActiveSessionId(null);
  };

  // A session keeps one jurisdiction: switching it starts a new chat. The
  // first render is skipped, it is not a switch.
  const previousJurisdiction = React.useRef(jurisdiction);
  React.useEffect(() => {
    if (previousJurisdiction.current === jurisdiction) return;
    previousJurisdiction.current = jurisdiction;
    if (activeSessionId === null) return;
    fetch("/api/chat/new-session", { method: "POST" })
      .catch(() => {
        // The local reset below must happen regardless.
      })
      .finally(startNewChat);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jurisdiction]);

  const handleSessionsDeleted = async (deletedId: string | null) => {
    if (activeSessionId === null) return;
    if (deletedId !== null && deletedId !== activeSessionId) return;
    try {
      await fetch("/api/chat/new-session", { method: "POST" });
    } catch {
      // The local reset below must happen regardless.
    } finally {
      startNewChat();
    }
  };

  const sendMessage = async (message: string) => {
    const generation = ++viewGeneration.current;
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setIsLoading(true);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ jurisdiction, language: locale, message }),
      });
      const viewUnchanged = viewGeneration.current === generation;
      if (!response.ok) {
        const notice = await chatErrorNotice(response, t, locale);
        if (viewUnchanged) {
          setMessages((prev) => [...prev, { role: "assistant", content: notice }]);
        }
        return;
      }
      const body: ChatApiResponse = await response.json();
      // A reply for another session than the active one means the backend
      // started a fresh session (e.g. after a jurisdiction switch): this
      // turn is its first, so only it is shown.
      const startedFreshSession = activeSessionId !== null && body.session_id !== activeSessionId;
      if (viewUnchanged) {
        const answer = assistantMessageView(body.answer, body.paragraphs, body.citations);
        setMessages((prev) =>
          body.session_id && startedFreshSession
            ? [{ role: "user", content: message }, answer]
            : [...prev, answer],
        );
      }
      if (body.session_id) {
        const isNewSession = activeSessionId === null || startedFreshSession;
        if (viewUnchanged) setActiveSessionId(body.session_id);
        // The server stored the answer either way.
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
