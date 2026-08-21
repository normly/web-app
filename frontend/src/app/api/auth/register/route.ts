// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { applySessionCookies } from "@/lib/session-cookies";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.json();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/register`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await backendResponse.json();
  const response = NextResponse.json(body, { status: backendResponse.status });
  if (backendResponse.ok && typeof body.session_token === "string") {
    applySessionCookies(response, { accountSessionToken: body.session_token });
  }
  return response;
}
