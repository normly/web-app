// frontend/tests/unit/admin-proxy-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { DELETE, GET, PATCH } from "@/app/api/admin/[...path]/route";

const originalFetch = global.fetch;
const ctx = (path: string[]) => ({ params: Promise.resolve({ path }) });

describe("/api/admin/[...path]", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards path, query and session to the accounts admin API", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ rows: [], total: 0 }), {
        status: 200, headers: { "content-type": "application/json" },
      }),
    );
    const request = new NextRequest("http://localhost/api/admin/users?q=a%40b&page=2", {
      headers: { cookie: "normly_account_session=tok" },
    });

    const response = await GET(request, ctx(["users"]));

    expect(response.status).toBe(200);
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://accounts.internal/v1/admin/users?q=a%40b&page=2");
    expect(init.headers.Authorization).toBe("Bearer tok");
  });

  it("passes JSON bodies and 204 answers through", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    const request = new NextRequest("http://localhost/api/admin/accounts/42", {
      method: "PATCH", body: JSON.stringify({ role: "user" }),
      headers: { cookie: "normly_account_session=tok", "content-type": "application/json" },
    });

    const response = await PATCH(request, ctx(["accounts", "42"]));

    expect(response.status).toBe(204);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ role: "user" }));
  });

  it("answers 401 without a session and refuses dot segments", async () => {
    const anonymous = new NextRequest("http://localhost/api/admin/users");
    expect((await GET(anonymous, ctx(["users"]))).status).toBe(401);
    const sneaky = new NextRequest("http://localhost/api/admin/x", {
      method: "DELETE", headers: { cookie: "normly_account_session=tok" },
    });
    expect((await DELETE(sneaky, ctx(["..", "accounts", "me"]))).status).toBe(400);
  });
});
