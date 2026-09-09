// frontend/src/lib/account-response.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

// accounts/ returns snake_case JSON (Pydantic's default, unconfigured). The
// pre-existing /api/auth/session route already translates account_id ->
// accountId for the frontend -- every other account-data BFF route follows
// the same camelCase convention here, rather than mixing raw snake_case
// bodies with this one already-translated shape.
export interface AccountSummary {
  accountId: string;
  email: string;
  firstName: string | null;
  lastName: string | null;
  avatarDataUrl: string | null;
  hasPassword: boolean;
  notificationPreference: string;
}

interface RawAccountFields {
  first_name: string | null;
  last_name: string | null;
  avatar_data_url: string | null;
  has_password: boolean;
  notification_preference: string;
}

export function mapAccountSummary(
  accountId: string, email: string, raw: RawAccountFields,
): AccountSummary {
  return {
    accountId, email, firstName: raw.first_name, lastName: raw.last_name,
    avatarDataUrl: raw.avatar_data_url, hasPassword: raw.has_password,
    notificationPreference: raw.notification_preference,
  };
}
