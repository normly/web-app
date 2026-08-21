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
});
