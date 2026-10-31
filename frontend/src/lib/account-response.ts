// frontend/src/lib/account-response.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

// accounts/ returns snake_case JSON (Pydantic's default, unconfigured). The
// pre-existing /api/auth/session route already translates account_id ->
// accountId for the frontend -- every other account-data BFF route follows
// the same camelCase convention here, rather than mixing raw snake_case
// bodies with this one already-translated shape.
export type AccountRole = "user" | "publisher" | "administrator";

export interface AccountSummary {
  accountId: string;
  email: string;
  firstName: string | null;
  lastName: string | null;
  hasAvatar: boolean;
  hasPassword: boolean;
  notificationPreference: string;
  // Only decides what the menu shows; the server checks the role again on
  // every admin request.
  role: AccountRole;
  publisherId: string | null;
}

interface RawAccountFields {
  first_name: string | null;
  last_name: string | null;
  has_avatar: boolean;
  has_password: boolean;
  notification_preference: string;
  role?: AccountRole;
  publisher_id?: string | null;
}

export function mapAccountSummary(
  accountId: string, email: string, raw: RawAccountFields,
): AccountSummary {
  return {
    accountId, email, firstName: raw.first_name, lastName: raw.last_name,
    hasAvatar: raw.has_avatar, hasPassword: raw.has_password,
    notificationPreference: raw.notification_preference,
    role: raw.role ?? "user", publisherId: raw.publisher_id ?? null,
  };
}
