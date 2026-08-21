// frontend/src/app/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { MessageList, type ChatMessageView } from "@/components/chat/message-list";
import { ChatInput } from "@/components/chat/chat-input";

interface ChatApiResponse {
  answer: string;
  answer_type: "structural" | "synthesis" | "fallback";
  citations: { document_id: string; segment_id: string | null }[];
}

export default function HomePage() {
  const [messages, setMessages] = React.useState<ChatMessageView[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);

  const sendMessage = async (message: string) => {
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setIsLoading(true);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ jurisdiction: "DE", language: "de", message }),
      });
      const body: ChatApiResponse = await response.json();
      const citations = await Promise.all(
        body.citations.map(async (citation) => {
          try {
            const documentResponse = await fetch(
              `/api/documents/${citation.document_id}?jurisdiction=DE`,
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
    <main className="mx-auto flex max-w-2xl flex-col gap-4 p-4">
      <MessageList messages={messages} isLoading={isLoading} />
      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </main>
  );
}
