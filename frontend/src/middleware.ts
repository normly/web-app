// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";

// Deliberately NOT `import { randomUUID } from "crypto"` -- Node's crypto
// module is not supported in the Edge Runtime middleware actually executes
// in at request time (this compiles and passes unit tests, which run
// middleware() directly in Node, but 500s on every real request once built
// and served: "The edge runtime does not support Node.js 'crypto' module").
// The Web Crypto API's global `crypto.randomUUID()` is the edge-compatible
// equivalent and is available in both the Edge Runtime and Node 19+.

const ANON_ID_COOKIE = "normly_anon_id";
const ANON_ID_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

// Runs before every request. A Server Component cannot set a cookie during
// render (layout.tsx's normly_locale/normly_jurisdiction pattern only ever
// READS a cookie server-side, relying on client-side document.cookie writes
// for changes) -- but normly_anon_id must exist and be STABLE from the very
// first request, before any user interaction, so it can't wait for a
// client-side write. Middleware is the one place in the App Router that can
// inspect and set a cookie ahead of every request uniformly, regardless of
// which page is hit first.
export function middleware(request: NextRequest): NextResponse {
  const response = NextResponse.next();
  if (!request.cookies.get(ANON_ID_COOKIE)) {
    response.cookies.set(ANON_ID_COOKIE, crypto.randomUUID(), {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: ANON_ID_MAX_AGE_SECONDS,
    });
  }
  return response;
}

export const config = {
  // Skip static assets and the service worker/manifest -- this cookie only
  // needs to exist before an actual page or API request, not before every
  // asset fetch.
  matcher: ["/((?!_next/static|_next/image|favicon|manifest|service-worker).*)"],
};
