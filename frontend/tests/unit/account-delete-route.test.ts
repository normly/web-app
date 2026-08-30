// frontend/tests/unit/account-delete-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/account/delete/route";

const originalFetch = global.fetch;

describe("POST /api/account/delete", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the password and clears the session cookie on success", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "account_deleted" }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/account/delete", {
      method: "POST", body: JSON.stringify({ password: "correct horse" }),
      headers: { cookie: "normly_account_session=acct-tok", "content-type": "application/json" },
    });
    const response = await POST(request);

    expect(response.status).toBe(200);
    expect(response.cookies.get("normly_account_session")?.value ?? "").toBe("");
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
    expect(JSON.parse(init.body)).toEqual({ password: "correct horse" });
  });

  it("does not clear the cookie when the backend rejects the password", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "password is incorrect" }), { status: 401 }),
    );

    const request = new NextRequest("http://localhost/api/account/delete", {
      method: "POST", body: JSON.stringify({ password: "wrong" }),
      headers: { cookie: "normly_account_session=acct-tok", "content-type": "application/json" },
    });
    const response = await POST(request);

    expect(response.status).toBe(401);
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/delete", {
      method: "POST", body: JSON.stringify({ password: null }),
      headers: { "content-type": "application/json" },
    });
    const response = await POST(request);
    expect(response.status).toBe(401);
  });
});
