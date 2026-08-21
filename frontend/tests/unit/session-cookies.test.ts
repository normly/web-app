// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { NextRequest, NextResponse } from "next/server";
import { applySessionCookies, readSessionCookies } from "@/lib/session-cookies";

describe("session cookies", () => {
  it("reads no cookies from a request that has none", () => {
    const request = new NextRequest("http://localhost/api/chat");
    expect(readSessionCookies(request)).toEqual({
      chatSessionToken: null,
      accountSessionToken: null,
    });
  });

  it("reads both cookies when present", () => {
    const request = new NextRequest("http://localhost/api/chat", {
      headers: { cookie: "normly_session=chat-tok; normly_account_session=account-tok" },
    });
    expect(readSessionCookies(request)).toEqual({
      chatSessionToken: "chat-tok",
      accountSessionToken: "account-tok",
    });
  });

  it("sets the chat session cookie as httpOnly on the response", () => {
    const response = NextResponse.json({ ok: true });
    applySessionCookies(response, { chatSessionToken: "new-chat-tok" });
    const cookie = response.cookies.get("normly_session");
    expect(cookie?.value).toBe("new-chat-tok");
    expect(cookie?.httpOnly).toBe(true);
  });

  it("sets the account session cookie as httpOnly on the response", () => {
    const response = NextResponse.json({ ok: true });
    applySessionCookies(response, { accountSessionToken: "new-account-tok" });
    const cookie = response.cookies.get("normly_account_session");
    expect(cookie?.value).toBe("new-account-tok");
    expect(cookie?.httpOnly).toBe(true);
  });
});
