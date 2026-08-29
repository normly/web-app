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
    const response = await GET(request, { params: { id: "abc" } });
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.status).toBe("valid");
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://api.internal/v1/documents/abc/validity?jurisdiction=DE");
  });
});
