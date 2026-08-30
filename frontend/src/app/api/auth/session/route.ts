// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";
import { mapAccountSummary } from "@/lib/account-response";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ account: null });
  }

  // cache: "no-store" is not optional here. Next.js's fetch Data Cache (and
  // its in-flight request de-duplication) is keyed loosely enough that two
  // near-simultaneous calls to this exact URL+Authorization pair -- which is
  // exactly what happens every time /account loads, since AppHeader and
  // AccountPageContent each independently fetch this route on mount -- can
  // resolve one of the two callers against the other's (or a stale) result.
  // Confirmed by direct measurement while building the Task 15 e2e suite:
  // 60/60 concurrent requests straight to the accounts backend never
  // misfired, but the identical pair of requests through this route handler
  // returned a false 401 in roughly a third of runs, which this route then
  // (incorrectly) treated as proof of a dead session and used to clear the
  // user's cookie -- logging out a user who had just successfully signed in.
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/session`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
    cache: "no-store",
  });
  if (!backendResponse.ok) {
    // The token the browser sent is expired/invalid -- stop it from
    // resending a dead token as Authorization on every subsequent
    // /api/chat/etc. call by clearing the stale cookie here too.
    const response = NextResponse.json({ account: null });
    response.cookies.delete("normly_account_session");
    return response;
  }
  const body = await backendResponse.json();
  return NextResponse.json({
    account: mapAccountSummary(body.account_id, body.email, body),
  });
}
