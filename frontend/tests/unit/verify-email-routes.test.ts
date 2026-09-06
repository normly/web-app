// frontend/tests/unit/verify-email-routes.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "@/app/api/auth/verify-email/route";
import { POST } from "@/app/api/auth/verify-email/resend/route";

const originalFetch = global.fetch;

describe("GET /api/auth/verify-email", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the token query param to the backend and relays the response", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "email_verified" }), { status: 200 }),
    );
    const request = new NextRequest("http://localhost/api/auth/verify-email?token=abc123");
    const response = await GET(request);
    expect(response.status).toBe(200);
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("/v1/accounts/verify-email?token=abc123");
  });

  it("relays a 400 for an invalid token", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
    );
    const request = new NextRequest("http://localhost/api/auth/verify-email?token=bad");
    const response = await GET(request);
    expect(response.status).toBe(400);
  });
});

describe("POST /api/auth/verify-email/resend", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the request body to the backend", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ status: "if_the_account_exists_and_is_unverified_an_email_was_sent" }),
        { status: 200 },
      ),
    );
    const request = new NextRequest("http://localhost/api/auth/verify-email/resend", {
      method: "POST",
      body: JSON.stringify({ email: "a@example.de" }),
    });
    const response = await POST(request);
    expect(response.status).toBe(200);
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("/v1/accounts/verify-email/resend");
    expect(JSON.parse(init.body as string)).toEqual({ email: "a@example.de" });
  });
});
