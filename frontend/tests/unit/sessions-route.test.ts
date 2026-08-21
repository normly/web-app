// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/chat/sessions/route";

const originalFetch = global.fetch;

describe("GET /api/chat/sessions", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("returns an empty list without calling the backend when there is no account cookie", async () => {
    global.fetch = vi.fn();
    const request = new NextRequest("http://localhost/api/chat/sessions");
    const response = await GET(request);
    const body = await response.json();
    expect(body).toEqual([]);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("returns 401 when there is no account cookie, so an anonymous visitor is told to log in", async () => {
    global.fetch = vi.fn();
    const request = new NextRequest("http://localhost/api/chat/sessions");
    const response = await GET(request);
    expect(response.status).toBe(401);
  });

  it("forwards the account cookie as Authorization and returns the backend's list", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "1", session_token: "tok-1", jurisdiction: "DE", language: "de",
            created_at: "2026-01-01T00:00:00Z",
          },
        ]),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/chat/sessions", {
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await GET(request);
    const body = await response.json();

    expect(body).toHaveLength(1);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });
});
