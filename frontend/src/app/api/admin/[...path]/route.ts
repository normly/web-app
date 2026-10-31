// frontend/src/app/api/admin/[...path]/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

type Context = { params: Promise<{ path: string[] }> };

// One pass-through for the whole admin API: the accounts service checks the
// role on every request, so this route only forwards the session. Segments
// are encoded one by one and dot segments are refused, so a path can never
// leave /v1/admin/.
async function proxy(request: NextRequest, { params }: Context): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }
  const { path } = await params;
  if (path.some((segment) => segment === "" || segment === "." || segment === "..")) {
    return NextResponse.json({ detail: "invalid path" }, { status: 400 });
  }
  const url =
    `${getBackendUrls().accounts}/v1/admin/${path.map(encodeURIComponent).join("/")}`
    + request.nextUrl.search;

  const headers: Record<string, string> = { Authorization: `Bearer ${accountSessionToken}` };
  const init: RequestInit = { method: request.method, headers, cache: "no-store" };
  if (request.method !== "GET" && request.method !== "HEAD") {
    const body = await request.text();
    if (body) {
      init.body = body;
      headers["content-type"] = "application/json";
    }
  }

  const backendResponse = await fetch(url, init);
  if (backendResponse.status === 204) {
    return new NextResponse(null, { status: 204 });
  }
  return new NextResponse(await backendResponse.text(), {
    status: backendResponse.status,
    headers: {
      "content-type": backendResponse.headers.get("content-type") ?? "application/json",
    },
  });
}

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE };
