// frontend/tests/unit/account-avatar-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors
//
// Runs under Node's environment rather than the suite's default jsdom:
// jsdom's FormData/Blob/Request implementations don't interop with
// next/server's NextRequest.formData() parsing -- request.formData() hangs
// indefinitely under jsdom (reproduced in isolation while debugging this
// file). Node's native fetch primitives parse it correctly.
// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST, DELETE } from "@/app/api/account/avatar/route";

const originalFetch = global.fetch;

describe("avatar BFF route", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards an uploaded file with the account session as Authorization", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "acc-1", email: "a@example.de", email_verified: true,
          first_name: null, last_name: null, has_avatar: true,
        }),
        { status: 200 },
      ),
    );
    const formData = new FormData();
    formData.append("avatar", new Blob([new Uint8Array([1, 2, 3])]), "avatar.jpg");

    const request = new NextRequest("http://localhost/api/account/avatar", {
      method: "POST", body: formData,
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await POST(request);
    const body = await response.json();

    expect(body.hasAvatar).toBe(true);
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("passes through a 400 from an invalid upload", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "avatar must be a valid image file" }), {
        status: 400,
      }),
    );
    const formData = new FormData();
    formData.append("avatar", new Blob([new Uint8Array([1])]), "not-an-image.txt");

    const request = new NextRequest("http://localhost/api/account/avatar", {
      method: "POST", body: formData,
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await POST(request);

    expect(response.status).toBe(400);
  });

  it("DELETE forwards the account session and maps the cleared response", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "acc-1", email: "a@example.de", email_verified: true,
          first_name: null, last_name: null, has_avatar: false,
        }),
        { status: 200 },
      ),
    );

    const request = new NextRequest("http://localhost/api/account/avatar", {
      method: "DELETE",
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await DELETE(request);
    const body = await response.json();

    expect(body.hasAvatar).toBe(false);
  });

  it("GET streams the image with its headers when the backend returns 200", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    const imageBytes = new Uint8Array([1, 2, 3, 4]);
    global.fetch = vi.fn().mockResolvedValue(
      new Response(imageBytes, {
        status: 200,
        headers: {
          "content-type": "image/jpeg",
          "etag": '"abc123"',
          "cache-control": "private, max-age=0, must-revalidate",
        },
      }),
    );

    const request = new NextRequest("http://localhost/api/account/avatar", {
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await GET(request);

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("image/jpeg");
    expect(response.headers.get("etag")).toBe('"abc123"');
    expect(response.headers.get("cache-control")).toBe("private, max-age=0, must-revalidate");
    const body = new Uint8Array(await response.arrayBuffer());
    expect(Array.from(body)).toEqual([1, 2, 3, 4]);
  });

  it("GET returns 304 with no body when the backend returns 304", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(null, {
        status: 304,
        headers: {
          "etag": '"abc123"',
          "cache-control": "private, max-age=0, must-revalidate",
        },
      }),
    );

    const request = new NextRequest("http://localhost/api/account/avatar", {
      headers: { cookie: "normly_account_session=acct-tok", "if-none-match": '"abc123"' },
    });
    const response = await GET(request);

    expect(response.status).toBe(304);
    expect(response.headers.get("etag")).toBe('"abc123"');
    expect(response.headers.get("cache-control")).toBe("private, max-age=0, must-revalidate");
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers["If-None-Match"]).toBe('"abc123"');
  });

  it("GET returns 404 when the backend has no avatar set", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "no avatar set" }), { status: 404 }),
    );

    const request = new NextRequest("http://localhost/api/account/avatar", {
      headers: { cookie: "normly_account_session=acct-tok" },
    });
    const response = await GET(request);

    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body).toEqual({ detail: "no avatar set" });
  });

  it("GET requires a session cookie", async () => {
    const request = new NextRequest("http://localhost/api/account/avatar");
    const response = await GET(request);
    expect(response.status).toBe(401);
  });
});
