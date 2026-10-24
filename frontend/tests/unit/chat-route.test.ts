// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/chat/route";

const originalFetch = global.fetch;

describe("POST /api/chat", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the request to chat/ and sets the returned session cookie", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_token: "new-session-token",
          answer: "Beispielantwort",
          answer_type: "synthesis",
          citations: [],
        }),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Testfrage" }),
      headers: { "content-type": "application/json" },
    });

    const response = await POST(request);
    const body = await response.json();

    expect(global.fetch).toHaveBeenCalledWith(
      "http://chat.internal/v1/chat",
      expect.objectContaining({ method: "POST" }),
    );
    expect(body.answer).toBe("Beispielantwort");
    expect(body.session_token).toBeUndefined();
    expect(response.cookies.get("normly_session")?.value).toBe("new-session-token");
  });

  it("forwards an existing account session cookie as an Authorization header", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_token: "tok", answer: "x", answer_type: "fallback", citations: [],
        }),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Testfrage" }),
      headers: {
        "content-type": "application/json",
        cookie: "normly_account_session=my-account-token",
      },
    });

    await POST(request);

    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer my-account-token");
  });

  it("sends no Authorization header when there is no account cookie (anonymous chat)", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_token: "tok", answer: "x", answer_type: "fallback", citations: [],
        }),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Testfrage" }),
      headers: { "content-type": "application/json" },
    });

    await POST(request);

    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBeUndefined();
    expect("Authorization" in init.headers).toBe(false);
  });

  it("passes through a 503 from chat/ without crashing", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "service temporarily unavailable" }), {
        status: 503,
      }),
    );

    const request = new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Testfrage" }),
      headers: { "content-type": "application/json" },
    });

    const response = await POST(request);
    expect(response.status).toBe(503);
  });

  it("sets no chat cookie when the backend returns a null session_token (anonymous)", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_token: null, answer: "x", answer_type: "fallback", citations: [],
        }),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Testfrage" }),
      headers: { "content-type": "application/json" },
    });

    const response = await POST(request);

    expect(response.cookies.get("normly_session")).toBeUndefined();
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("clears an existing chat cookie when the backend returns no session_token", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_token: null, answer: "x", answer_type: "fallback", citations: [],
        }),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Testfrage" }),
      headers: { "content-type": "application/json", cookie: "normly_session=stale-token" },
    });

    const response = await POST(request);

    const setCookie = response.headers.get("set-cookie") ?? "";
    expect(setCookie).toContain("normly_session=;");
    expect(setCookie.toLowerCase()).toMatch(/max-age=0/);
  });

  it("keeps the chat cookie when the backend answers with an error (503)", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "service temporarily unavailable" }), {
        status: 503,
      }),
    );

    const request = new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Testfrage" }),
      headers: {
        "content-type": "application/json",
        cookie: "normly_session=live-token; normly_account_session=my-account-token",
      },
    });

    const response = await POST(request);

    expect(response.status).toBe(503);
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("forwards the anonymous caller headers to chat/", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ answer: "a", answer_type: "synthesis", citations: [] }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Frage" }),
      headers: {
        "content-type": "application/json",
        cookie: "normly_anon_id=anon-123",
        "x-forwarded-for": "1.2.3.4",
      },
    });
    await POST(request);

    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers).toMatchObject({
      "X-Normly-Anon-Id": "anon-123",
      "X-Forwarded-For": "1.2.3.4",
    });
  });

  it("passes a 429 body through unchanged", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    const detail = { reason: "quota_exhausted", resets_at: "2026-10-23T00:00:00Z", anonymous: true };
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail }), { status: 429 }));

    const response = await POST(new NextRequest("http://localhost/api/chat", {
      method: "POST",
      body: JSON.stringify({ jurisdiction: "DE", language: "de", message: "Frage" }),
      headers: { "content-type": "application/json" },
    }));

    expect(response.status).toBe(429);
    expect(await response.json()).toEqual({ detail });
  });
});
