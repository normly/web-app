// frontend/src/lib/rate-limit-headers.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { NextRequest } from "next/server";

// Forwards the anonymous rate-limiting identifier (set by middleware.ts)
// and the incoming X-Forwarded-For header on every proxied api/ call, so
// api/'s rate limiter can key on the real caller instead of collapsing
// every BFF-proxied request into one shared bucket keyed on this
// container's own address.
export function rateLimitHeaders(request: NextRequest): Record<string, string> {
  const anonId = request.cookies.get("normly_anon_id")?.value;
  const forwardedFor = request.headers.get("x-forwarded-for");
  return {
    ...(anonId ? { "X-Normly-Anon-Id": anonId } : {}),
    ...(forwardedFor ? { "X-Forwarded-For": forwardedFor } : {}),
  };
}
