// frontend/tests/unit/chat-new-session-route.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";
import { POST } from "@/app/api/chat/new-session/route";

describe("POST /api/chat/new-session", () => {
  it("clears the chat session cookie", async () => {
    const request = new NextRequest("http://localhost/api/chat/new-session", {
      method: "POST",
      headers: { cookie: "normly_session=old-token" },
    });
    const response = await POST(request);
    expect(response.status).toBe(200);
    const setCookie = response.headers.get("set-cookie") ?? "";
    expect(setCookie).toContain("normly_session=;");
  });
});
