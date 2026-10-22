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

  // Uncached for the same reason as /api/account/sessions: a session-scoped GET.
  const backendResponse = await fetch(`${getBackendUrls().chat}/v1/chat/usage`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
    cache: "no-store",
  });
  const body = await backendResponse.json().catch(() => ({}));
  return NextResponse.json(body, { status: backendResponse.status });
}
