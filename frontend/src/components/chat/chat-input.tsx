// frontend/src/components/chat/chat-input.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { ArrowUp } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

export function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (message: string) => void;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const [value, setValue] = React.useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  return (
    <div className="flex items-center gap-2 rounded-lg border bg-background p-2">
      <Textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        placeholder={t("chat.inputPlaceholder")}
        disabled={disabled}
        aria-label={t("chat.inputPlaceholder")}
        className="min-h-[88px] resize-none border-0 shadow-none focus-visible:ring-0"
      />
      <Button
        onClick={submit}
        disabled={disabled}
        size="icon"
        className="shrink-0"
        aria-label={t("chat.sendButton")}
      >
        <ArrowUp className="h-4 w-4" />
      </Button>
    </div>
  );
}
