// frontend/src/app/api/account/notifications/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";
import { readSessionCookies } from "@/lib/session-cookies";

interface RawNotification {
  id: string;
  work_id: string;
  trigger_type: string;
  trigger_document_id: string | null;
  trigger_jurisdiction: string | null;
  created_at: string;
  read_at: string | null;
}

function mapNotification(raw: RawNotification) {
  return {
    id: raw.id, workId: raw.work_id, triggerType: raw.trigger_type,
    triggerDocumentId: raw.trigger_document_id, triggerJurisdiction: raw.trigger_jurisdiction,
    createdAt: raw.created_at, readAt: raw.read_at,
  };
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { accountSessionToken } = readSessionCookies(request);
  if (!accountSessionToken) {
    return NextResponse.json({ detail: "not authenticated" }, { status: 401 });
  }
  const backendResponse = await fetch(`${getBackendUrls().accounts}/v1/accounts/notifications`, {
    headers: { Authorization: `Bearer ${accountSessionToken}` },
    cache: "no-store",
  });
  if (!backendResponse.ok) {
    return NextResponse.json(await backendResponse.json(), { status: backendResponse.status });
  }
  const body: RawNotification[] = await backendResponse.json();
  return NextResponse.json(body.map(mapNotification));
}
