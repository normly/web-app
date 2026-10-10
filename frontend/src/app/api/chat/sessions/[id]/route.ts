// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "account session required" }, { status: 401 });
  }
  const { id } = await params;

  const backendResponse = await fetch(
    `${getBackendUrls().chat}/v1/chat/sessions/${encodeURIComponent(id)}`,
    { method: "DELETE", headers: { Authorization: `Bearer ${accountSessionToken}` } },
  );
  if (backendResponse.status === 204) {
    return new NextResponse(null, { status: 204 });
  }
  const body = await backendResponse.json().catch(() => ({}));
  return NextResponse.json(body, { status: backendResponse.status });
}
