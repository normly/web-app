// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET as getMessages } from "@/app/api/chat/sessions/[id]/messages/route";
import { POST as postTitle } from "@/app/api/chat/sessions/[id]/title/route";
import { GET as getCurrent } from "@/app/api/chat/current/route";

const originalFetch = global.fetch;

function request(url: string, cookie?: string, method = "GET"): NextRequest {
  return new NextRequest(url, { method, headers: cookie ? { cookie } : {} });
}

const MESSAGES_BODY = {
  session_id: "sess-1",
  session_token: "chat-tok-1",
  title: "Titel",
  messages: [],
};

describe("GET /api/chat/sessions/[id]/messages", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards the account token, strips the session token and sets the chat cookie", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(MESSAGES_BODY), { status: 200 }));

    const response = await getMessages(
      request("http://localhost/api/chat/sessions/sess-1/messages", "normly_account_session=acct"),
      { params: Promise.resolve({ id: "sess-1" }) },
    );

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.session_token).toBeUndefined();
    expect(body.title).toBe("Titel");
    expect(response.cookies.get("normly_session")?.value).toBe("chat-tok-1");
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://chat.internal/v1/chat/sessions/sess-1/messages");
    expect(init.headers.Authorization).toBe("Bearer acct");
  });

  it("answers 401 without an account cookie and does not call the backend", async () => {
    global.fetch = vi.fn();
    const response = await getMessages(request("http://localhost/api/chat/sessions/x/messages"), {
      params: Promise.resolve({ id: "x" }),
    });
    expect(response.status).toBe(401);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("passes a 404 through without touching the cookie", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "nope" }), { status: 404 }));
    const response = await getMessages(
      request("http://localhost/api/chat/sessions/x/messages", "normly_account_session=acct"),
      { params: Promise.resolve({ id: "x" }) },
    );
    expect(response.status).toBe(404);
    expect(response.cookies.get("normly_session")).toBeUndefined();
  });
});

describe("POST /api/chat/sessions/[id]/title", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("proxies the title request with the account token", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ title: "T" }), { status: 200 }));

    const response = await postTitle(
      request("http://localhost/api/chat/sessions/sess-1/title", "normly_account_session=acct", "POST"),
      { params: Promise.resolve({ id: "sess-1" }) },
    );

    expect(await response.json()).toEqual({ title: "T" });
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://chat.internal/v1/chat/sessions/sess-1/title");
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer acct");
  });

  it("answers 401 without an account cookie", async () => {
    global.fetch = vi.fn();
    const response = await postTitle(request("http://localhost/api/chat/sessions/x/title", undefined, "POST"), {
      params: Promise.resolve({ id: "x" }),
    });
    expect(response.status).toBe(401);
  });
});

describe("GET /api/chat/current", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("restores the session the chat cookie names", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "http://chat.internal/v1/chat/sessions") {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              { id: "other", session_token: "chat-tok-0" },
              { id: "sess-1", session_token: "chat-tok-1" },
            ]),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify(MESSAGES_BODY), { status: 200 }));
    });

    const response = await getCurrent(
      request("http://localhost/api/chat/current", "normly_account_session=acct; normly_session=chat-tok-1"),
    );

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.session_id).toBe("sess-1");
    expect(body.session_token).toBeUndefined();
    const urls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map(([u]) => u);
    expect(urls).toEqual([
      "http://chat.internal/v1/chat/sessions",
      "http://chat.internal/v1/chat/sessions/sess-1/messages",
    ]);
  });

  it("answers 204 when a cookie is missing or no session matches", async () => {
    vi.stubEnv("NORMLY_CHAT_BASE_URL", "http://chat.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

    expect((await getCurrent(request("http://localhost/api/chat/current"))).status).toBe(204);
    expect(
      (await getCurrent(request("http://localhost/api/chat/current", "normly_account_session=acct"))).status,
    ).toBe(204);
    expect(
      (
        await getCurrent(
          request("http://localhost/api/chat/current", "normly_account_session=acct; normly_session=gone"),
        )
      ).status,
    ).toBe(204);
  });
});
