// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { TranslationKey } from "@/lib/i18n/dictionary-keys";
import { interpolate } from "@/lib/i18n/interpolate";
import { formatResetTime } from "@/lib/reset-time";

// Mirrors NORMLY_CHAT_MAX_MESSAGE_CHARS' default; the server's 400 stays the
// backstop if an operator lowers it.
export const MAX_MESSAGE_CHARS = 2000;

interface BudgetDetail {
  reason: string;
  resets_at: string;
  anonymous: boolean;
}

function isBudgetDetail(value: unknown): value is BudgetDetail {
  const detail = value as BudgetDetail | null;
  return (
    typeof detail === "object" && detail !== null &&
    typeof detail.reason === "string" && typeof detail.resets_at === "string"
  );
}

// The assistant-bubble text for a failed chat request.
export async function chatErrorNotice(
  response: Response,
  t: (key: TranslationKey) => string,
  locale: string,
  now: Date = new Date(),
): Promise<string> {
  const body = await response.json().catch(() => null);
  const detail = body?.detail;
  if (response.status === 429 && isBudgetDetail(detail)) {
    const time = formatResetTime(detail.resets_at, locale, now);
    const key: TranslationKey =
      detail.reason === "quota_exhausted"
        ? detail.anonymous ? "chat.quotaExhaustedAnonymous" : "chat.quotaExhausted"
        : detail.anonymous ? "chat.poolExhaustedAnonymous" : "chat.poolExhausted";
    return interpolate(t(key), { time });
  }
  if (response.status === 400 && detail === "message_too_long") {
    return interpolate(t("chat.messageTooLong"), { max: String(MAX_MESSAGE_CHARS) });
  }
  return t("chat.errorAnswer");
}
