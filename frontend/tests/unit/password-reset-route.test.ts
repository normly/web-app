// frontend/tests/unit/password-reset-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST as requestReset } from "@/app/api/auth/password-reset/request/route";
import { POST as confirmReset } from "@/app/api/auth/password-reset/confirm/route";

const originalFetch = global.fetch;

describe("password reset BFF routes", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("forwards a reset request to the backend", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "if_the_account_exists_an_email_was_sent" }), {
        status: 200,
      }),
    );

    const request = new NextRequest("http://localhost/api/auth/password-reset/request", {
      method: "POST", body: JSON.stringify({ email: "a@example.de" }),
      headers: { "content-type": "application/json" },
    });
    const response = await requestReset(request);

    expect(response.status).toBe(200);
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://accounts.internal/v1/accounts/password-reset/request");
  });

  it("forwards a confirm request to the backend", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "password_changed" }), { status: 200 }),
    );

    const request = new NextRequest("http://localhost/api/auth/password-reset/confirm", {
      method: "POST",
      body: JSON.stringify({ token: "tok", new_password: "new secret" }),
      headers: { "content-type": "application/json" },
    });
    const response = await confirmReset(request);

    expect(response.status).toBe(200);
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("http://accounts.internal/v1/accounts/password-reset/confirm");
  });

  it("passes through a 400 from an invalid confirm token", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid or expired token" }), { status: 400 }),
    );

    const request = new NextRequest("http://localhost/api/auth/password-reset/confirm", {
      method: "POST", body: JSON.stringify({ token: "bad", new_password: "x" }),
      headers: { "content-type": "application/json" },
    });
    const response = await confirmReset(request);

    expect(response.status).toBe(400);
  });
});
