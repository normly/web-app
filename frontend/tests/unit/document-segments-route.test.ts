// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "@/app/api/documents/[id]/segments/route";

const originalFetch = global.fetch;

describe("GET /api/documents/[id]/segments", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("proxies to api/ with the jurisdiction and passes status and body through", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify([{ id: "s1" }]), { status: 200 }));

    const response = await GET(
      new NextRequest("http://localhost/api/documents/doc-1/segments?jurisdiction=AT"),
      { params: Promise.resolve({ id: "doc-1" }) },
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual([{ id: "s1" }]);
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://api.internal/v1/documents/doc-1/segments?jurisdiction=AT");
  });

  it("passes a 404 through", async () => {
    vi.stubEnv("NORMLY_API_BASE_URL", "http://api.internal");
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ detail: "document not found" }), { status: 404 }));

    const response = await GET(
      new NextRequest("http://localhost/api/documents/doc-1/segments"),
      { params: Promise.resolve({ id: "doc-1" }) },
    );

    expect(response.status).toBe(404);
  });
});
