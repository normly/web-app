// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import de from "@/lib/i18n/de.json";
import { chatErrorNotice } from "@/lib/chat-error-notice";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

const t = (key: TranslationKey) =>
  key.split(".").reduce<unknown>((node, part) => (node as Record<string, unknown>)[part], de) as string;
const now = new Date("2026-10-22T19:00:00Z");

function limited(detail: unknown): Response {
  return new Response(JSON.stringify({ detail }), { status: 429 });
}

describe("chatErrorNotice", () => {
  it("tells an anonymous user to sign in when their quota is spent", async () => {
    const notice = await chatErrorNotice(
      limited({ reason: "quota_exhausted", resets_at: "2026-10-23T00:00:00Z", anonymous: true }),
      t, "de", now,
    );
    expect(notice).toContain("Melde dich an");
  });

  it("names only the reset time for a registered user's spent quota", async () => {
    const notice = await chatErrorNotice(
      limited({ reason: "quota_exhausted", resets_at: "2026-10-23T00:00:00Z", anonymous: false }),
      t, "de", now,
    );
    expect(notice).toContain("Du hast heute alle KI-Antworten genutzt");
  });

  it("says that search and norm information keep working when a pool is spent", async () => {
    for (const reason of ["pool_daily_exhausted", "pool_monthly_exhausted"]) {
      const notice = await chatErrorNotice(
        limited({ reason, resets_at: "2026-11-01T00:00:00Z", anonymous: true }), t, "de", now,
      );
      expect(notice).toContain("Suche und Normauskünfte");
    }
  });

  it("explains an oversized message", async () => {
    const response = new Response(JSON.stringify({ detail: "message_too_long" }), { status: 400 });
    expect(await chatErrorNotice(response, t, "de", now)).toContain("2000 Zeichen");
  });

  it("falls back to the generic error for anything else", async () => {
    const response = new Response("oops", { status: 503 });
    expect(await chatErrorNotice(response, t, "de", now)).toBe(t("chat.errorAnswer"));
  });
});
