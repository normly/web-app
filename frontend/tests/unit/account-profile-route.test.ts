// frontend/tests/unit/account-profile-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { PATCH } from "@/app/api/account/profile/route";

const originalFetch = global.fetch;

describe("PATCH /api/account/profile", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account session as Authorization and maps the response", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "acc-1", email: "a@example.de", email_verified: true,
          first_name: "Jamie", last_name: "Tester", has_avatar: false,
        }),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/account/profile", {
      method: "PATCH", body: JSON.stringify({ first_name: "Jamie", last_name: "Tester" }),
      headers: { cookie: "normly_account_session=acct-tok", "content-type": "application/json" },
    });
    const response = await PATCH(request);
    const body = await response.json();

    expect(body).toEqual({
      accountId: "acc-1", email: "a@example.de", firstName: "Jamie", lastName: "Tester",
      hasAvatar: false,
    });
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("returns 401 without an account session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/profile", {
      method: "PATCH", body: JSON.stringify({ first_name: "x", last_name: "y" }),
      headers: { "content-type": "application/json" },
    });
    const response = await PATCH(request);
    expect(response.status).toBe(401);
  });
});
