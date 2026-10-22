// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/account/usage/route";

const originalFetch = global.fetch;

describe("GET /api/account/usage", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("answers 401 without an account session", async () => {
    global.fetch = vi.fn();
    const response = await GET(new NextRequest("http://localhost/api/account/usage"));

    expect(response.status).toBe(401);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("asks chat/ with the account token, uncached, and passes the body through", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    const usage = {
      used: 7, limit: 30, resets_at: "2026-10-23T00:00:00Z", pool_exhausted: false, pool_resets_at: null,
    };
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(usage), { status: 200 }));

    const response = await GET(new NextRequest("http://localhost/api/account/usage", {
      headers: { cookie: "normly_account_session=account-token" },
    }));

    expect(global.fetch).toHaveBeenCalledWith("http://chat.internal/v1/chat/usage", {
      headers: { Authorization: "Bearer account-token" },
      cache: "no-store",
    });
    expect(await response.json()).toEqual(usage);
  });
});
