// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { applySessionCookies, clearChatSessionCookie, readSessionCookies } from "@/lib/session-cookies";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.json();
  const { chatSessionToken, accountSessionToken } = readSessionCookies(request);

  const headers: Record<string, string> = { "content-type": "application/json" };
  if (accountSessionToken) {
    headers.Authorization = `Bearer ${accountSessionToken}`;
  }

  const backendResponse = await fetch(`${getBackendUrls().chat}/v1/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({ ...payload, session_token: chatSessionToken }),
  });

  const body = await backendResponse.json();
  const response = NextResponse.json(body, { status: backendResponse.status });

  if (backendResponse.ok && typeof body.session_token === "string") {
    applySessionCookies(response, { chatSessionToken: body.session_token });
  } else if (chatSessionToken) {
    // No token back (anonymous, or an error): a stale chat cookie must not linger.
    clearChatSessionCookie(response);
  }

  return response;
}
