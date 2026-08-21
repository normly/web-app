// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest, NextResponse } from "next/server";
import { getBackendUrls } from "@/lib/backend-urls";

// This GET handler takes no request param and calls no dynamic API, so
// Next.js would otherwise treat it as statically optimizable and evaluate
// it at build time -- where getBackendUrls() throws, since env vars are
// read at runtime (see next.config.mjs), not baked into the build. Force
// dynamic rendering so the redirect target is resolved per-request instead.
export const dynamic = "force-dynamic";

// A plain redirect, not a fetch-and-relay: accounts/'s own /google/login
// itself redirects to Google, and the browser needs to follow that chain
// with a real navigation, not something a Route Handler can proxy through
// fetch().
export async function GET(): Promise<NextResponse> {
  return NextResponse.redirect(`${getBackendUrls().accounts}/v1/accounts/google/login`);
}
