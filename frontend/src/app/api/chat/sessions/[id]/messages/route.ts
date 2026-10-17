// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { applySessionCookies, readSessionCookies } from "@/lib/session-cookies";

// Opening a session makes it the active one: the chat cookie is pointed at
// it, so the next /api/chat POST continues this conversation. The token
// itself stays server-side, like every other chat token.
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "account session required" }, { status: 401 });
  }
  const { id } = await params;
  const backendResponse = await fetch(
    `${getBackendUrls().chat}/v1/chat/sessions/${encodeURIComponent(id)}/messages`,
    { headers: { Authorization: `Bearer ${accountSessionToken}` } },
  );
  const body = await backendResponse.json().catch(() => ({}));
  if (!backendResponse.ok) {
    return NextResponse.json(body, { status: backendResponse.status });
  }
  const { session_token: chatSessionToken, ...rest } = body;
  const response = NextResponse.json(rest);
  applySessionCookies(response, { chatSessionToken });
  return response;
}
