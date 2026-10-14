// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { NextRequest, NextResponse } from "next/server";

const CHAT_SESSION_COOKIE = "normly_session";
const ACCOUNT_SESSION_COOKIE = "normly_account_session";

// 30 days matches accounts/'s own sliding-window session lifetime
// (extended server-side on every successful /v1/accounts/session check);
// the cookie's own max-age is a client-side courtesy, not the source of
// truth -- the backend always re-validates the token regardless.
const ACCOUNT_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30;
// The chat cookie is only ever set for logged-in accounts: anonymous chats
// are not stored, so the backend returns no session token for them. It has
// no defined server-side TTL -- 90 days is a reasonable client-side default,
// not a claim about backend expiry.
const CHAT_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 90;

export interface SessionCookies {
  chatSessionToken: string | null;
  accountSessionToken: string | null;
}

export function readSessionCookies(request: NextRequest): SessionCookies {
  return {
    chatSessionToken: request.cookies.get(CHAT_SESSION_COOKIE)?.value ?? null,
    accountSessionToken: request.cookies.get(ACCOUNT_SESSION_COOKIE)?.value ?? null,
  };
}

export function applySessionCookies(
  response: NextResponse,
  tokens: { chatSessionToken?: string; accountSessionToken?: string },
): void {
  const isProduction = process.env.NODE_ENV === "production";
  if (tokens.chatSessionToken) {
    response.cookies.set(CHAT_SESSION_COOKIE, tokens.chatSessionToken, {
      httpOnly: true,
      secure: isProduction,
      sameSite: "lax",
      path: "/",
      maxAge: CHAT_COOKIE_MAX_AGE_SECONDS,
    });
  }
  if (tokens.accountSessionToken) {
    response.cookies.set(ACCOUNT_SESSION_COOKIE, tokens.accountSessionToken, {
      httpOnly: true,
      secure: isProduction,
      sameSite: "lax",
      path: "/",
      maxAge: ACCOUNT_COOKIE_MAX_AGE_SECONDS,
    });
  }
}

// Removes the chat cookie (e.g. when the backend returned no session token,
// so a stale token from before logout or from a legacy anonymous chat must go).
export function clearChatSessionCookie(response: NextResponse): void {
  response.cookies.set(CHAT_SESSION_COOKIE, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
}
