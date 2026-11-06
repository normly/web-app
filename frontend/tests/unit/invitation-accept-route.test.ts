// frontend/tests/unit/invitation-accept-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/auth/invitation/accept/route";

const originalFetch = global.fetch;

describe("POST /api/auth/invitation/accept", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("sets the session cookie on success", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ session_token: "new-session", account: {} }), { status: 200 }),
    );
    const response = await POST(new NextRequest("http://localhost/api/auth/invitation/accept", {
      method: "POST", body: JSON.stringify({ token: "inv" }),
      headers: { "content-type": "application/json" },
    }));
    expect(response.status).toBe(200);
    expect(response.cookies.get("normly_account_session")?.value).toBe("new-session");
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://accounts.internal/v1/accounts/invitations/accept");
  });

  it("passes errors through without a cookie", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invitation_invalid" }), { status: 410 }),
    );
    const response = await POST(new NextRequest("http://localhost/api/auth/invitation/accept", {
      method: "POST", body: JSON.stringify({ token: "old" }),
      headers: { "content-type": "application/json" },
    }));
    expect(response.status).toBe(410);
    expect(response.cookies.get("normly_account_session")).toBeUndefined();
  });
});
