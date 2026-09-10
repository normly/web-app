// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/documents/[id]/validity/route";

const originalFetch = global.fetch;

describe("GET /api/documents/[id]/validity", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("proxies to the backend validity endpoint", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "valid" }), { status: 200 }),
    );

    const request = new NextRequest(
      "http://localhost/api/documents/abc/validity?jurisdiction=DE",
    );
    const response = await GET(request, { params: Promise.resolve({ id: "abc" }) });
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.status).toBe("valid");
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://api.internal/v1/documents/abc/validity?jurisdiction=DE");
  });
  it("forwards the normly_anon_id cookie as an X-Normly-Anon-Id header", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "valid" }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/documents/abc/validity", {
      headers: { cookie: "normly_anon_id=anon-123" },
    });
    await GET(request, { params: Promise.resolve({ id: "abc" }) });

    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers["X-Normly-Anon-Id"]).toBe("anon-123");
  });
});
