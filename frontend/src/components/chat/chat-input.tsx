// frontend/src/components/chat/chat-input.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { ArrowUp } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

const MAX_HEIGHT_PX = 260; // ~3x the 88px resting height this replaces (user-approved, rounded)

export function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (message: string) => void;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const [value, setValue] = React.useState("");
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  React.useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;

    const resize = () => {
      if (value === "") {
        el.style.height = "";
        el.style.overflowY = "hidden";
        return;
      }
      el.style.height = "auto";
      const contentHeight = el.scrollHeight;
      el.style.height = `${Math.min(contentHeight, MAX_HEIGHT_PX)}px`;
      el.style.overflowY = contentHeight > MAX_HEIGHT_PX ? "auto" : "hidden";
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(el);
    return () => observer.disconnect();
  }, [value]);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  return (
    <div className="flex items-center gap-2 rounded-lg border bg-background p-2">
      <Textarea
        ref={textareaRef}
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
        className="min-h-[44px] resize-none border-0 shadow-none focus-visible:ring-0"
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
