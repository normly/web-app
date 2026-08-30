// frontend/tests/unit/account-response.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { mapAccountSummary } from "@/lib/account-response";

describe("mapAccountSummary", () => {
  it("maps the backend's snake_case fields to the frontend's camelCase shape", () => {
    const result = mapAccountSummary("acc-1", "a@example.de", {
      first_name: "Jamie", last_name: "Weber", avatar_data_url: "data:image/jpeg;base64,xyz",
    });

    expect(result).toEqual({
      accountId: "acc-1", email: "a@example.de", firstName: "Jamie", lastName: "Weber",
      avatarDataUrl: "data:image/jpeg;base64,xyz",
    });
  });

  it("preserves null fields", () => {
    const result = mapAccountSummary("acc-2", "b@example.de", {
      first_name: null, last_name: null, avatar_data_url: null,
    });

    expect(result.firstName).toBeNull();
    expect(result.lastName).toBeNull();
    expect(result.avatarDataUrl).toBeNull();
  });
});
