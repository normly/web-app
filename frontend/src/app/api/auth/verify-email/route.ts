// frontend/src/app/api/auth/verify-email/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const token = request.nextUrl.searchParams.get("token") ?? "";
  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/verify-email?token=${encodeURIComponent(token)}`,
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
