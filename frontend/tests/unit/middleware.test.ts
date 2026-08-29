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
});
