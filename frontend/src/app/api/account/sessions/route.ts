// frontend/src/app/api/account/sessions/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  // See the comment in /api/auth/session/route.ts -- an uncached fetch is
  // required for any session-scoped GET, not just that one route, to avoid
  // Next.js's fetch Data Cache serving a stale or cross-request result for
  // near-simultaneous identical requests.
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/sessions`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
    cache: "no-store",
  });
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
