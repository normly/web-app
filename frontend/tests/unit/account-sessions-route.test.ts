// frontend/tests/unit/account-sessions-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/account/sessions/route";
import { DELETE } from "@/app/api/account/sessions/[sessionId]/route";

const originalFetch = global.fetch;

describe("GET /api/account/sessions", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account session and returns the list", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "sess-1", created_at: "2026-08-01T00:00:00Z",
            expires_at: "2026-09-01T00:00:00Z", is_current: true,
          },
        ]),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/account/sessions", {
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await GET(request);
    const body = await response.json();

    expect(body).toHaveLength(1);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/sessions");
    const response = await GET(request);
    expect(response.status).toBe(401);
  });
});

describe("DELETE /api/account/sessions/[sessionId]", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account session and the session id", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "session_revoked" }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/account/sessions/sess-2", {
      method: "DELETE", headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await DELETE(request, { params: Promise.resolve({ sessionId: "sess-2" }) });

    expect(response.status).toBe(200);
    const [calledUrl, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(calledUrl).toBe("http://accounts.internal/v1/accounts/sessions/sess-2");
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/sessions/sess-2", {
      method: "DELETE",
    });
    const response = await DELETE(request, { params: Promise.resolve({ sessionId: "sess-2" }) });
    expect(response.status).toBe(401);
  });
});
