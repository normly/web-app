// frontend/src/app/api/account/avatar/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";
import { mapAccountSummary } from "@/lib/account-response";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const formData = await request.formData();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/avatar`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accountSessionToken}` },
    body: formData,
  });
  const body = await backendResponse.json();
  if (!backendResponse.ok) {
    return NextResponse.json(body, { status: backendResponse.status });
  }
  return NextResponse.json(mapAccountSummary(body.id, body.email, body));
}

export async function DELETE(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/avatar`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${accountSessionToken}` },
  });
  const body = await backendResponse.json();
  if (!backendResponse.ok) {
    return NextResponse.json(body, { status: backendResponse.status });
  }
  return NextResponse.json(mapAccountSummary(body.id, body.email, body));
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }

  const headers: Record<string, string> = { Authorization: `Bearer ${accountSessionToken}` };
  const ifNoneMatch = request.headers.get("if-none-match");
  if (ifNoneMatch) {
    headers["If-None-Match"] = ifNoneMatch;
  }

  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/avatar`, {
    headers,
    cache: "no-store",
  });

  if (backendResponse.status === 304) {
    return new NextResponse(null, { status: 304 });
  }
  if (backendResponse.status === 404) {
    const body = await backendResponse.json();
    return NextResponse.json(body, { status: 404 });
  }

  const body = await backendResponse.arrayBuffer();
  return new NextResponse(body, {
    status: backendResponse.status,
    headers: {
      "Content-Type": backendResponse.headers.get("content-type") ?? "application/octet-stream",
      "ETag": backendResponse.headers.get("etag") ?? "",
      "Cache-Control":
        backendResponse.headers.get("cache-control") ?? "private, max-age=0, must-revalidate",
    },
  });
}
