// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { rateLimitHeaders } from "@/lib/rate-limit-headers";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const incoming = request.nextUrl.searchParams;
  const forwarded = new URLSearchParams();
  forwarded.set("jurisdiction", incoming.get("jurisdiction") ?? "DE");
  const q = incoming.get("q");
  if (q) forwarded.set("q", q);
  const issuer = incoming.get("issuer");
  if (issuer) forwarded.set("issuer", issuer);
  const limit = incoming.get("limit");
  if (limit) forwarded.set("limit", limit);
  const offset = incoming.get("offset");
  if (offset) forwarded.set("offset", offset);

  const backendResponse = await fetch(
    `${getBackendUrls().api}/v1/documents/search?${forwarded.toString()}`,
    { headers: rateLimitHeaders(request) },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
