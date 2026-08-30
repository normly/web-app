// frontend/tests/unit/account-password-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/account/password/route";

const originalFetch = global.fetch;

describe("POST /api/account/password", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account session and the password payload", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "password_set" }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/account/password", {
      method: "POST",
      body: JSON.stringify({ current_password: "old", new_password: "new secret" }),
      headers: { cookie: "normly_account_session=acct-tok", "content-type": "application/json" },
    });
    const response = await POST(request);

    expect(response.status).toBe(200);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/password", {
      method: "POST", body: JSON.stringify({ current_password: null, new_password: "x" }),
      headers: { "content-type": "application/json" },
    });
    const response = await POST(request);
    expect(response.status).toBe(401);
  });
});
