// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

// accounts/'s POST /v1/accounts/logout (see
// accounts/src/normly_accounts/routers/login.py) takes the token to revoke
// as a JSON body field (`{ session_token }`), not an Authorization header --
// unlike GET /v1/accounts/session, it has no auth dependency of its own.
export async function POST(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);

  if (accountSessionToken) {
    try {
      await fetch(`${getBackendUrls().accounts}/v1/accounts/logout`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ session_token: accountSessionToken }),
      });
    } catch {
      // Best-effort revoke: whether or not accounts/ is reachable, the
      // cookie is cleared below either way, so the browser stops sending
      // this token regardless of whether the backend actually revoked it.
    }
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.delete("normly_account_session");
  return response;
}
