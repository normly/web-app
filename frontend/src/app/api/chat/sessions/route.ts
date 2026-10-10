// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    // No cookie at all means a genuinely anonymous visitor, not "logged in
    // with zero sessions" -- report it the same way the backend reports an
    // invalid/expired token (401), so ChatsPageContent can always tell
    // "not authenticated" apart from "authenticated, empty history".
    return NextResponse.json([], { status: 401 });
  }

  const backendResponse = await fetch(`${getBackendUrls().chat}/v1/chat/sessions`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
  });
  if (!backendResponse.ok) {
    return NextResponse.json([], { status: backendResponse.status });
  }
  const body = await backendResponse.json();
  return NextResponse.json(body);
}

export async function DELETE(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "account session required" }, { status: 401 });
  }
  const backendResponse = await fetch(`${getBackendUrls().chat}/v1/chat/sessions`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${accountSessionToken}` },
  });
  const body = await backendResponse.json().catch(() => ({}));
  return NextResponse.json(body, { status: backendResponse.status });
}
