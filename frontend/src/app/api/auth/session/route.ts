// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ account: null });
  }

  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/session`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
  });
  if (!backendResponse.ok) {
    return NextResponse.json({ account: null });
  }
  const body = await backendResponse.json();
  return NextResponse.json({ account: { accountId: body.account_id, email: body.email } });
}
