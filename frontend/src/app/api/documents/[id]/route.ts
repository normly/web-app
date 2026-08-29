// frontend/src/app/api/documents/[id]/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { rateLimitHeaders } from "@/lib/rate-limit-headers";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } },
): Promise<NextResponse> {
  const jurisdiction = request.nextUrl.searchParams.get("jurisdiction") ?? "DE";
  const backendResponse = await fetch(
    `${getBackendUrls().api}/v1/documents/${encodeURIComponent(params.id)}` +
      `?jurisdiction=${encodeURIComponent(jurisdiction)}`,
    { headers: rateLimitHeaders(request) },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
