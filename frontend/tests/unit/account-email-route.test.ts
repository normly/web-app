// frontend/tests/unit/account-email-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/account/email/route";
import { GET } from "@/app/api/account/email/confirm/route";

const originalFetch = global.fetch;

describe("POST /api/account/email", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account session and the new email", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "confirmation_sent" }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/account/email", {
      method: "POST", body: JSON.stringify({ new_email: "new@example.de" }),
      headers: { cookie: "normly_account_session=acct-tok", "content-type": "application/json" },
    });
    const response = await POST(request);

    expect(response.status).toBe(200);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
    expect(JSON.parse(init.body)).toEqual({ new_email: "new@example.de" });
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/email", {
      method: "POST", body: JSON.stringify({ new_email: "new@example.de" }),
      headers: { "content-type": "application/json" },
    });
    const response = await POST(request);
    expect(response.status).toBe(401);
  });
});

describe("GET /api/account/email/confirm", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the token and email query params without requiring a session", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "email_changed" }), { status: 200 }),
    );

    const request = new NextRequest(
      "http://localhost/api/account/email/confirm?token=tok-1&email=new@example.de",
    );
    const response = await GET(request);

    expect(response.status).toBe(200);
    const [calledUrl] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(calledUrl).toBe(
      "http://accounts.internal/v1/accounts/email/confirm?token=tok-1&email=new%40example.de",
    );
  });

  it("passes through a 400 for an invalid token", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
    );

    const request = new NextRequest(
      "http://localhost/api/account/email/confirm?token=bad&email=new@example.de",
    );
    const response = await GET(request);

    expect(response.status).toBe(400);
  });
});
