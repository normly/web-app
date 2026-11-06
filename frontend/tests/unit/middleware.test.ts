// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "@/middleware";

describe("middleware", () => {
  it("sets normly_anon_id when the cookie is missing", () => {
    const request = new NextRequest("http://localhost/");
    const response = middleware(request);
    const cookie = response.cookies.get("normly_anon_id");
    expect(cookie?.value).toBeTruthy();
    expect(cookie?.httpOnly).toBe(true);
  });

  it("leaves an existing normly_anon_id untouched", () => {
    const request = new NextRequest("http://localhost/", {
      headers: { cookie: "normly_anon_id=existing-value" },
    });
    const response = middleware(request);
    expect(response.cookies.get("normly_anon_id")).toBeUndefined();
  });

  it("sends /admin/* without an account session to /login", () => {
    const response = middleware(new NextRequest("http://localhost/admin/users"));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost/login");
  });

  it("lets /admin/* through with an account session cookie", () => {
    const response = middleware(new NextRequest("http://localhost/admin/users", {
      headers: { cookie: "normly_account_session=tok" },
    }));
    expect(response.headers.get("location")).toBeNull();
  });
});
