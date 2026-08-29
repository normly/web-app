// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/documents/search/route";

const originalFetch = global.fetch;

describe("GET /api/documents/search", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards q/issuer/jurisdiction/limit/offset and returns the backend body", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ results: [], total: 0 }), { status: 200 }),
    );

    const request = new NextRequest(
      "http://localhost/api/documents/search?q=Vorschrift&issuer=DGUV&jurisdiction=DE&limit=10&offset=5",
    );
    const response = await GET(request);
    const body = await response.json();

    expect(body).toEqual({ results: [], total: 0 });
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("http://api.internal/v1/documents/search?");
    expect(url).toContain("q=Vorschrift");
    expect(url).toContain("issuer=DGUV");
    expect(url).toContain("jurisdiction=DE");
    expect(url).toContain("limit=10");
    expect(url).toContain("offset=5");
  });

  it("defaults jurisdiction to DE when absent", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ results: [], total: 0 }), { status: 200 }),
    );

    await GET(new NextRequest("http://localhost/api/documents/search"));

    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("jurisdiction=DE");
  });

  it("forwards the normly_anon_id cookie as an X-Normly-Anon-Id header", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ results: [], total: 0 }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/documents/search", {
      headers: { cookie: "normly_anon_id=anon-123" },
    });
    await GET(request);

    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers["X-Normly-Anon-Id"]).toBe("anon-123");
  });

  it("passes through a 429 from the backend", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "rate limit exceeded" }), { status: 429 }),
    );

    const response = await GET(new NextRequest("http://localhost/api/documents/search"));

    expect(response.status).toBe(429);
  });
});
