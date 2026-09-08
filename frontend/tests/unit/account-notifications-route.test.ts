// frontend/tests/unit/account-notifications-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/account/notifications/route";
import { PATCH } from "@/app/api/account/notifications/[id]/route";

const originalFetch = global.fetch;

describe("/api/account/notifications", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("returns 401 for GET without an account cookie", async () => {
    global.fetch = vi.fn();
    const response = await GET(new NextRequest("http://localhost/api/account/notifications"));
    expect(response.status).toBe(401);
  });

  it("forwards PATCH for a given notification id", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "n1", read_at: "2026-01-01T00:00:00Z" }), { status: 200 }),
    );
    const request = new NextRequest("http://localhost/api/account/notifications/n1", {
      method: "PATCH",
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await PATCH(request, { params: Promise.resolve({ id: "n1" }) });
    expect(response.status).toBe(200);
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://accounts.internal/v1/accounts/notifications/n1");
    expect(init.method).toBe("PATCH");
  });
});
