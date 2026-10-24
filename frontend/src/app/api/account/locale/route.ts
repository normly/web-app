// frontend/src/app/api/account/locale/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

// The language switch calls this for every visitor: the session cookie is
// httpOnly, so only this route can tell whether there is an account whose
// stored mail language should follow the switch.
export async function PUT(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return new NextResponse(null, { status: 204 });
  }

  const { locale } = await request.json();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/profile`, {
    method: "PATCH",
    headers: {
      "content-type": "application/json", Authorization: `Bearer ${accountSessionToken}`,
    },
    body: JSON.stringify({ locale }),
  });
  return new NextResponse(null, { status: backendResponse.ok ? 204 : backendResponse.status });
}
