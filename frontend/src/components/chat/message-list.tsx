// frontend/src/components/chat/message-list.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { useTranslation } from "@/lib/i18n/provider";
import { CitationChip, type CitationView } from "@/components/chat/citation-chip";

export interface ChatMessageView {
  role: "user" | "assistant";
  content: string;
  citations?: CitationView[];
}

export function MessageList({
  messages,
  isLoading,
}: {
  messages: ChatMessageView[];
  isLoading: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-4" role="log" aria-live="polite">
      {messages.map((message, index) => (
        <div
          key={index}
          className={message.role === "user" ? "self-end text-right" : "self-start"}
        >
          <p>{message.content}</p>
          {message.citations && message.citations.length > 0 && (
            <div className="mt-1 flex gap-2">
              {message.citations.map((citation) => (
                <CitationChip key={citation.documentId} citation={citation} />
              ))}
            </div>
          )}
        </div>
      ))}
      {isLoading && <p aria-busy="true">{t("chat.loading")}</p>}
    </div>
  );
}
