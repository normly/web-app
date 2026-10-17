// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

// The chat cookie is httpOnly, so the page cannot tell which session is
// active. This route answers that on page load: the session list carries
// each session's token, the cookie names one of them.
export async function GET(request: NextRequest): Promise<NextResponse> {
  const { chatSessionToken, accountSessionToken } = readSessionCookies(request);
  if (!chatSessionToken || !accountSessionToken) {
    return new NextResponse(null, { status: 204 });
  }
  try {
    return await restoreCurrent(chatSessionToken, accountSessionToken);
  } catch {
    return new NextResponse(null, { status: 204 });
  }
}

async function restoreCurrent(chatSessionToken: string, accountSessionToken: string): Promise<NextResponse> {
  const headers = { Authorization: `Bearer ${accountSessionToken}` };
  const listResponse = await fetch(`${getBackendUrls().chat}/v1/chat/sessions`, { headers });
  if (!listResponse.ok) {
    return new NextResponse(null, { status: 204 });
  }
  const sessions: { id: string; session_token: string }[] = await listResponse.json();
  const active = sessions.find((session) => session.session_token === chatSessionToken);
  if (!active) {
    return new NextResponse(null, { status: 204 });
  }
  const messagesResponse = await fetch(
    `${getBackendUrls().chat}/v1/chat/sessions/${encodeURIComponent(active.id)}/messages`,
    { headers },
  );
  if (!messagesResponse.ok) {
    return new NextResponse(null, { status: 204 });
  }
  const { session_token: _token, ...body } = await messagesResponse.json();
  return NextResponse.json(body);
}
