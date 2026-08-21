// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST as login } from "@/app/api/auth/login/route";
import { POST as magicLinkRequest } from "@/app/api/auth/magic-link/request/route";
import { GET as session } from "@/app/api/auth/session/route";

const originalFetch = global.fetch;

describe("auth Route Handlers", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("login sets the account session cookie on success", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_token: "acct-tok",
          account: { id: "1", email: "a@example.de", email_verified: true },
        }),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "a@example.de", password: "correct horse battery staple" }),
      headers: { "content-type": "application/json" },
    });
    const response = await login(request);

    expect(response.status).toBe(200);
    expect(response.cookies.get("normly_account_session")?.value).toBe("acct-tok");
  });

  it("login passes through a 401 without setting a cookie", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid email or password" }), { status: 401 }),
    );

    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "a@example.de", password: "wrong" }),
      headers: { "content-type": "application/json" },
    });
    const response = await login(request);

    expect(response.status).toBe(401);
    expect(response.cookies.get("normly_account_session")).toBeUndefined();
  });

  it("magic-link request forwards the payload without needing a cookie", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "if_the_account_exists_an_email_was_sent" }), {
        status: 200,
      }),
    );

    const request = new NextRequest("http://localhost/api/auth/magic-link/request", {
      method: "POST",
      body: JSON.stringify({ email: "a@example.de" }),
      headers: { "content-type": "application/json" },
    });
    const response = await magicLinkRequest(request);
    expect(response.status).toBe(200);
  });

  it("session check returns null-account for a missing cookie without calling the backend", async () => {
    global.fetch = vi.fn();
    const request = new NextRequest("http://localhost/api/auth/session");
    const response = await session(request);
    const body = await response.json();
    expect(body).toEqual({ account: null });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("session check returns the account for a valid cookie", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ account_id: "1", email: "a@example.de" }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/auth/session", {
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await session(request);
    const body = await response.json();
    expect(body.account).toEqual({ accountId: "1", email: "a@example.de" });
  });
});
