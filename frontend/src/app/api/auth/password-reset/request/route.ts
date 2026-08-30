// frontend/src/app/api/auth/password-reset/request/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.json();
  const backendResponse = await fetch(
    `${getBackendUrls().accounts}/v1/accounts/password-reset/request`,
    {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const body = await backendResponse.json();
  return NextResponse.json(body, { status: backendResponse.status });
}
