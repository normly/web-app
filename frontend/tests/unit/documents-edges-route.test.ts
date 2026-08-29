// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/documents/[id]/edges/route";

const originalFetch = global.fetch;

describe("GET /api/documents/[id]/edges", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("proxies to the backend edges endpoint with encoded id/jurisdiction", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

    const request = new NextRequest(
      "http://localhost/api/documents/abc/edges?jurisdiction=DE",
    );
    const response = await GET(request, { params: { id: "abc" } });

    expect(response.status).toBe(200);
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://api.internal/v1/documents/abc/edges?jurisdiction=DE");
  });

  it("percent-encodes a path-traversal id instead of forwarding it raw", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

    const request = new NextRequest(
      "http://localhost/api/documents/..%2F..%2Fadmin/edges?jurisdiction=DE",
    );
    await GET(request, { params: { id: "../../admin" } });

    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).not.toContain("/../../admin/");
    expect(url).toContain(encodeURIComponent("../../admin"));
  });
});
