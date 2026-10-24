// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { PUT } from "@/app/api/account/locale/route";

const originalFetch = global.fetch;

function request(cookie?: string) {
  return new NextRequest("http://localhost/api/account/locale", {
    method: "PUT",
    body: JSON.stringify({ locale: "en" }),
    headers: { "content-type": "application/json", ...(cookie ? { cookie } : {}) },
  });
}

describe("PUT /api/account/locale", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("answers 204 without calling the backend when nobody is signed in", async () => {
    global.fetch = vi.fn();
    const response = await PUT(request());
    expect(response.status).toBe(204);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("stores the locale on the signed-in account", async () => {
    vi.stubEnv("NORMLY_ACCOUNTS_BASE_URL", "http://accounts.internal");
    global.fetch = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));

    const response = await PUT(request("normly_account_session=acct-tok"));

    expect(response.status).toBe(204);
    expect(global.fetch).toHaveBeenCalledWith(
      "http://accounts.internal/v1/accounts/profile",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ locale: "en" }),
        headers: expect.objectContaining({ Authorization: "Bearer acct-tok" }),
      }),
    );
  });
});
