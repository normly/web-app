// frontend/src/app/api/chat/new-session/route.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextResponse } from "next/server";

// "Neuer Chat" needs no backend call: the chat session is purely a
// client-cookie concept (see session-cookies.ts) that the next /api/chat
// POST re-creates from scratch once this cookie is gone -- mirrors the
// same response.cookies.delete(...) pattern already used by
// /api/auth/logout for the account-session cookie.
export async function POST(): Promise<NextResponse> {
  const response = NextResponse.json({ ok: true });
  response.cookies.delete("normly_session");
  return response;
}
