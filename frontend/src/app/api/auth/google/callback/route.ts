// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { applySessionCookies } from "@/lib/session-cookies";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const error = request.nextUrl.searchParams.get("error");

  const forwardedParams = new URLSearchParams();
  if (code) forwardedParams.set("code", code);
  if (state) forwardedParams.set("state", state);
  if (error) forwardedParams.set("error", error);

  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/google/callback?${forwardedParams.toString()}`,
  );
  const body = await backendResponse.json();

  if (!backendResponse.ok) {
    return NextResponse.redirect(new URL("/?auth_error=1", request.url));
  }

  const response = NextResponse.redirect(new URL("/", request.url));
  if (typeof body.session_token === "string") {
    applySessionCookies(response, { accountSessionToken: body.session_token });
  }
  return response;
}
