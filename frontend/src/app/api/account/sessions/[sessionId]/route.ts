// frontend/src/app/api/account/sessions/[sessionId]/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function DELETE(
  request: NextRequest, { params }: { params: Promise<{ sessionId: string }> },
): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const { sessionId } = await params;
  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/sessions/${sessionId}`,
    { method: "DELETE", headers: { Authorization: `Bearer ${accountSessionToken}` } },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
