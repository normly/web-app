// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { DELETE as deleteOne } from "@/app/api/chat/sessions/[id]/route";
import { DELETE as deleteAll } from "@/app/api/chat/sessions/route";

const originalFetch = global.fetch;

function request(url: string, cookie?: string): NextRequest {
  return new NextRequest(url, {
    method: "DELETE",
    headers: cookie ? { cookie } : {},
  });
}

describe("DELETE /api/chat/sessions/[id]", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account Bearer token and passes 204 through", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));

    const response = await deleteOne(
      request("http://localhost/api/chat/sessions/abc", "normly_account_session=acct-tok"),
      { params: Promise.resolve({ id: "abc" }) },
    );

    expect(response.status).toBe(204);
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://chat.internal/v1/chat/sessions/abc");
    expect(init.method).toBe("DELETE");
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("answers 401 without calling the backend when there is no account cookie", async () => {
    global.fetch = vi.fn();
    const response = await deleteOne(request("http://localhost/api/chat/sessions/abc"), {
      params: Promise.resolve({ id: "abc" }),
    });
    expect(response.status).toBe(401);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("passes a 404 from the backend through", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ detail: "nope" }), { status: 404 }));
    const response = await deleteOne(
      request("http://localhost/api/chat/sessions/abc", "normly_account_session=t"),
      { params: Promise.resolve({ id: "abc" }) },
    );
    expect(response.status).toBe(404);
  });
});

describe("DELETE /api/chat/sessions", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the Bearer token and returns the deleted count", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ deleted: 3 }), { status: 200 }));

    const response = await deleteAll(
      request("http://localhost/api/chat/sessions", "normly_account_session=acct-tok"),
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ deleted: 3 });
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://chat.internal/v1/chat/sessions");
    expect(init.method).toBe("DELETE");
    expect(init.headers.Authorization).toBe("Bearer acct-tok");
  });

  it("answers 401 without calling the backend when there is no account cookie", async () => {
    global.fetch = vi.fn();
    const response = await deleteAll(request("http://localhost/api/chat/sessions"));
    expect(response.status).toBe(401);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
