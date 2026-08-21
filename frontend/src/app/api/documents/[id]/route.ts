// frontend/src/app/api/documents/[id]/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } },
): Promise<NextResponse> {
  const jurisdiction = request.nextUrl.searchParams.get("jurisdiction") ?? "DE";
  const backendResponse = await fetch(
    `${getBackendUrls().api}/v1/documents/${params.id}?jurisdiction=${jurisdiction}`,
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
