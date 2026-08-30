// frontend/src/app/api/account/avatar/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";
import { mapAccountSummary } from "@/lib/account-response";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const formData = await request.formData();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/avatar`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accountSessionToken}` },
    body: formData,
  });
  const body = await backendResponse.json();
  if (!backendResponse.ok) {
    return NextResponse.json(body, { status: backendResponse.status });
  }
  return NextResponse.json(mapAccountSummary(body.id, body.email, body));
}

export async function DELETE(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/avatar`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${accountSessionToken}` },
  });
  const body = await backendResponse.json();
  if (!backendResponse.ok) {
    return NextResponse.json(body, { status: backendResponse.status });
  }
  return NextResponse.json(mapAccountSummary(body.id, body.email, body));
}
