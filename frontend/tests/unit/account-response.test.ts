// frontend/tests/unit/account-response.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { mapAccountSummary } from "@/lib/account-response";

describe("mapAccountSummary", () => {
  it("maps the backend's snake_case fields to the frontend's camelCase shape", () => {
    const result = mapAccountSummary("acc-1", "a@example.de", {
      first_name: "Jamie", last_name: "Tester", has_avatar: true,
      has_password: true, notification_preference: "immediate",
    });

    expect(result).toEqual({
      accountId: "acc-1", email: "a@example.de", firstName: "Jamie", lastName: "Tester",
      hasAvatar: true, hasPassword: true,
      notificationPreference: "immediate",
    });
  });

  it("preserves null fields", () => {
    const result = mapAccountSummary("acc-2", "b@example.de", {
      first_name: null, last_name: null, has_avatar: false, has_password: false,
      notification_preference: "none",
    });

    expect(result.firstName).toBeNull();
    expect(result.lastName).toBeNull();
    expect(result.hasAvatar).toBe(false);
    expect(result.hasPassword).toBe(false);
  });

  it("echoes the notification preference from the raw fields", () => {
    const result = mapAccountSummary("acc-3", "c@example.de", {
      first_name: null, last_name: null, has_avatar: false, has_password: false,
      notification_preference: "digest",
    });

    expect(result.notificationPreference).toBe("digest");
  });
});
