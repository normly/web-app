// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

export interface BackendUrls {
  api: string;
  accounts: string;
  chat: string;
}

// Read per-request (not module-scope constants) so tests can stub env vars
// freely without import-order surprises, matching the pattern already used
// by lib/config.ts.
//
// Each property is a getter, not a plain value: a Route Handler that only
// ever reads e.g. `.accounts` (like /api/auth/login) must not be forced to
// also have NORMLY_API_BASE_URL/NORMLY_CHAT_BASE_URL set just because this
// object happened to validate all three eagerly. Getters defer requireEnv()
// until the specific property is actually accessed.
export function getBackendUrls(): BackendUrls {
  return {
    get api() {
      return requireEnv("NORMLY_API_BASE_URL");
    },
    get accounts() {
      return requireEnv("NORMLY_ACCOUNTS_BASE_URL");
    },
    get chat() {
      return requireEnv("NORMLY_CHAT_BASE_URL");
    },
  };
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is not set`);
  }
  return value;
}
