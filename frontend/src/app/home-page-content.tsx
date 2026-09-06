// frontend/src/app/home-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors
//
// Split out of page.tsx for the same reason chats/chats-page-content.tsx
// is: page.tsx now needs to be a Server Component (it calls
// getInstanceConfig(), which reads process.env and is only meaningful
// server-side -- see AppHeader's comment) so it can pass instanceName/
// logoPath down as props, while the chat state/hooks below need a client
// component.

"use client";

import * as React from "react";
import { MessageList, type ChatMessageView } from "@/components/chat/message-list";
import { ChatInput } from "@/components/chat/chat-input";
import { ChatShell } from "@/components/chat/chat-shell";
import { useTranslation } from "@/lib/i18n/provider";
import { useJurisdiction } from "@/lib/jurisdiction/provider";

interface ChatApiResponse {
  answer: string;
  answer_type: "structural" | "synthesis" | "fallback";
  citations: { document_id: string; segment_id: string | null }[];
}

export function HomePageContent() {
  const { locale } = useTranslation();
  const { jurisdiction } = useJurisdiction();
  const [messages, setMessages] = React.useState<ChatMessageView[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);

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
      const citations = await Promise.all(
        body.citations.map(async (citation) => {
          try {
            const documentResponse = await fetch(
              `/api/documents/${citation.document_id}?jurisdiction=${jurisdiction}`,
            );
            const document = await documentResponse.json();
            return { documentId: citation.document_id, href: document.source?.retrieval_path ?? null };
          } catch {
            return { documentId: citation.document_id, href: null };
          }
        }),
      );
      setMessages((prev) => [...prev, { role: "assistant", content: body.answer, citations }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <ChatShell onNewChat={() => setMessages([])}>
      <div className="mx-auto flex max-w-2xl flex-1 flex-col gap-4 p-4">
        <MessageList messages={messages} isLoading={isLoading} />
        <ChatInput onSend={sendMessage} disabled={isLoading} />
      </div>
    </ChatShell>
  );
}
