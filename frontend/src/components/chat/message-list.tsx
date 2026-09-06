// frontend/src/components/chat/message-list.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";
import { CitationChip, type CitationView } from "@/components/chat/citation-chip";

export interface ChatMessageView {
  role: "user" | "assistant";
  content: string;
  citations?: CitationView[];
}

function CopyButton({ content }: { content: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-7 w-7"
      onClick={handleCopy}
      aria-label={copied ? t("chat.copiedLabel") : t("chat.copyButtonLabel")}
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </Button>
  );
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
    <div className="flex flex-col gap-6" role="log" aria-live="polite">
      {messages.map((message, index) =>
        message.role === "user" ? (
          <div key={index} className="flex justify-end">
            <p className="max-w-[80%] whitespace-pre-wrap rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground">
              {message.content}
            </p>
          </div>
        ) : (
          <div key={index} className="flex flex-col gap-2">
            <p className="whitespace-pre-wrap text-sm text-foreground">{message.content}</p>
            {message.citations && message.citations.length > 0 && (
              <div className="flex gap-2">
                {message.citations.map((citation) => (
                  <CitationChip key={citation.documentId} citation={citation} />
                ))}
              </div>
            )}
            <CopyButton content={message.content} />
          </div>
        ),
      )}
      {isLoading && (
        <p aria-busy="true" className="text-sm text-muted-foreground">
          {t("chat.loading")}
        </p>
      )}
    </div>
  );
}
