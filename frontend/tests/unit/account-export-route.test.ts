// frontend/tests/unit/account-export-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/account/export/route";

const originalFetch = global.fetch;

describe("GET /api/account/export", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account session and returns the export payload", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    const exportBody = {
      account: {
        email: "a@example.de", created_at: "2026-01-01T00:00:00Z", email_verified: true,
        google_linked: false, first_name: null, last_name: null, avatar_data_url: null,
      },
      chat_sessions: [],
    };
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(exportBody), { status: 200 }));

    const request = new NextRequest("http://localhost/api/account/export", {
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await GET(request);
    const body = await response.json();

    expect(body).toEqual(exportBody);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/export");
    const response = await GET(request);
    expect(response.status).toBe(401);
  });
});
