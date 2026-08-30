// frontend/src/app/api/account/delete/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const payload = await request.json();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/me`, {
    method: "DELETE",
    headers: {
      "content-type": "application/json", Authorization: `Bearer ${accountSessionToken}`,
    },
    body: JSON.stringify(payload),
  });
  const body = await backendResponse.json();
  const response = NextResponse.json(body, { status: backendResponse.status });
  if (backendResponse.ok) {
    response.cookies.delete("normly_account_session");
  }
  return response;
}
