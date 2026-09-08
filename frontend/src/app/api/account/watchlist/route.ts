// frontend/src/app/api/account/watchlist/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

interface RawWatchlistEntry {
  work_id: string;
  created_at: string;
}

function mapEntry(raw: RawWatchlistEntry) {
  return { workId: raw.work_id, createdAt: raw.created_at };
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/watchlist`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
    cache: "no-store",
  });
  if (!backendResponse.ok) {
    return NextResponse.json(await backendResponse.json(), { status: backendResponse.status });
  }
  const body: RawWatchlistEntry[] = await backendResponse.json();
  return NextResponse.json(body.map(mapEntry));
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }
  const payload = await request.json();
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/watchlist`, {
    method: "POST",
    headers: {
      "content-type": "application/json", Authorization: `Bearer ${accountSessionToken}`,
    },
    body: JSON.stringify({ work_id: payload.workId }),
  });
  const body = await backendResponse.json();
  if (!backendResponse.ok) {
    return NextResponse.json(body, { status: backendResponse.status });
  }
  return NextResponse.json(mapEntry(body));
}
