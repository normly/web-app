// frontend/src/app/api/account/email/confirm/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

// No session cookie is read or required here -- the link is followed from
// an email client, possibly in a different browser/session than the one
// that requested the change. Task 5's confirm endpoint re-validates the
// token and the address's availability on its own; this route is a plain
// query-string-forwarding proxy.
export async function GET(request: NextRequest): Promise<NextResponse> {
  const token = request.nextUrl.searchParams.get("token") ?? "";
  const email = request.nextUrl.searchParams.get("email") ?? "";

  const backendUrl = new URL(`${getBackendUrls().accounts}/v1/accounts/email/confirm`);
  backendUrl.searchParams.set("token", token);
  backendUrl.searchParams.set("email", email);

  const backendResponse = await fetch(backendUrl.toString());
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
