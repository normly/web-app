// frontend/tests/unit/account-watchlist-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "@/app/api/account/watchlist/route";
import { DELETE } from "@/app/api/account/watchlist/[workId]/route";

const originalFetch = global.fetch;

describe("/api/account/watchlist", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("returns 401 for GET without an account cookie", async () => {
    global.fetch = vi.fn();
    const response = await GET(new NextRequest("http://localhost/api/account/watchlist"));
    expect(response.status).toBe(401);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("forwards POST with the account cookie as Authorization", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ work_id: "11111111-1111-1111-1111-111111111111", created_at: "2026-01-01T00:00:00Z" }),
        { status: 200 },
      ),
    );
    const request = new NextRequest("http://localhost/api/account/watchlist", {
      method: "POST",
      headers: { cookie: "normly_account_session=acct-tok", "content-type": "application/json" },
      body: JSON.stringify({ workId: "11111111-1111-1111-1111-111111111111" }),
    });
    const response = await POST(request);
    const body = await response.json();
    expect(body.workId).toBe("11111111-1111-1111-1111-111111111111");
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
    expect(JSON.parse(init.body)).toEqual({ work_id: "11111111-1111-1111-1111-111111111111" });
  });

  it("forwards DELETE for a given workId", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "removed" }), { status: 200 }));
    const request = new NextRequest("http://localhost/api/account/watchlist/work-1", {
      method: "DELETE",
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await DELETE(request, { params: Promise.resolve({ workId: "work-1" }) });
    expect(response.status).toBe(200);
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://accounts.internal/v1/accounts/watchlist/work-1");
  });
});
