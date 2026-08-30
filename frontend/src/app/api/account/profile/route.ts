// frontend/src/app/api/account/profile/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";
import { mapAccountSummary } from "@/lib/account-response";

export async function PATCH(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const payload = await request.json();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/profile`, {
    method: "PATCH",
    headers: {
      "content-type": "application/json", Authorization: `Bearer ${accountSessionToken}`,
    },
    body: JSON.stringify(payload),
  });
  const body = await backendResponse.json();
  if (!backendResponse.ok) {
    return NextResponse.json(body, { status: backendResponse.status });
  }
  return NextResponse.json(mapAccountSummary(body.id, body.email, body));
}
