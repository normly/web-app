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
export function getBackendUrls(): BackendUrls {
  return {
    api: requireEnv("NORMLY_API_BASE_URL"),
    accounts: requireEnv("NORMLY_ACCOUNTS_BASE_URL"),
    chat: requireEnv("NORMLY_CHAT_BASE_URL"),
  };
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is not set`);
  }
  return value;
}
