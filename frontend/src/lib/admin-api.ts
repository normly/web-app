// frontend/src/lib/admin-api.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

export type Role = "user" | "publisher" | "administrator";
export type UserStatus = "active" | "blocked" | "invited" | "expired";
export type BlockReason = "bulk_retrieval" | "abuse" | "terms_violation" | "other";
export type SortKey =
  | "email" | "first_name" | "last_name" | "sign_in" | "role" | "publisher"
  | "last_login_at" | "created_at" | "status";

export const ROLES: Role[] = ["user", "publisher", "administrator"];
export const BLOCK_REASONS: BlockReason[] = ["bulk_retrieval", "abuse", "terms_violation", "other"];
export const PAGE_SIZES = [10, 20, 50] as const;

export interface UsersQuery {
  q: string;
  role: Role | "all";
  status: UserStatus | "all";
  sort: SortKey;
  order: "asc" | "desc";
  page: number;
  pageSize: number;
}

export interface AdminUserRow {
  kind: "account" | "invitation";
  id: string;
  email: string;
  firstName: string | null;
  lastName: string | null;
  signInMethods: Array<"email" | "google">;
  role: Role;
  publisherId: string | null;
  publisherName: string | null;
  lastLoginAt: string | null;
  createdAt: string | null;
  status: UserStatus;
  blockReason: BlockReason | null;
  expiresAt: string | null;
}

export interface AdminUserPage { rows: AdminUserRow[]; total: number; page: number; pageSize: number }

export interface AdminSummary {
  accountsTotal: number;
  accountsActive30Days: number;
  accountsByRole: Record<Role, number>;
  publishersWithAccounts: number;
  openInvitations: number;
  blocked: number;
  mostFrequentBlockReason: BlockReason | null;
}

export interface Publisher { id: string; name: string }
export interface InvitationCheck {
  existingAccount: boolean; verified: boolean; blocked: boolean; openInvitation: boolean;
}
export interface InviteInput {
  email: string; role: Role; publisherId: string | null; locale: "de" | "en"; message: string;
}
export interface RoleMatrix {
  roles: string[];
  rows: Array<{ capability: string; planned: boolean; values: Record<string, string> }>;
}

export class AdminApiError extends Error {
  constructor(public status: number, public code: string) {
    super(code);
    this.name = "AdminApiError";
  }
}

const KNOWN_CODES = new Set([
  "last_administrator", "self_action", "upgrade_requires_invitation", "not_a_publisher",
  "account_blocked", "already_blocked", "not_blocked", "publisher_name_taken",
  "unknown_publisher", "confirmation_mismatch", "invitation_invalid", "forbidden",
]);

export function errorKey(error: unknown): TranslationKey {
  if (error instanceof AdminApiError && KNOWN_CODES.has(error.code)) {
    return `admin.errors.${error.code}` as TranslationKey;
  }
  return "admin.errors.generic";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/admin/${path}`, {
    ...init,
    headers: init?.body ? { "content-type": "application/json" } : undefined,
  });
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new AdminApiError(response.status, typeof body.detail === "string" ? body.detail : "generic");
  }
  return body as T;
}

type Raw = any;

function mapRow(raw: Raw): AdminUserRow {
  return {
    kind: raw.kind, id: raw.id, email: raw.email, firstName: raw.first_name,
    lastName: raw.last_name, signInMethods: raw.sign_in_methods, role: raw.role,
    publisherId: raw.publisher_id, publisherName: raw.publisher_name,
    lastLoginAt: raw.last_login_at, createdAt: raw.created_at, status: raw.status,
    blockReason: raw.block_reason, expiresAt: raw.expires_at,
  };
}

function usersSearch(query: UsersQuery): string {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.role !== "all") params.set("role", query.role);
  if (query.status !== "all") params.set("status", query.status);
  params.set("sort", query.sort);
  params.set("order", query.order);
  params.set("page", String(query.page));
  params.set("page_size", String(query.pageSize));
  return params.toString();
}

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });

export const adminApi = {
  async listUsers(query: UsersQuery): Promise<AdminUserPage> {
    const raw = await request<Raw>(`users?${usersSearch(query)}`);
    return { rows: raw.rows.map(mapRow), total: raw.total, page: raw.page, pageSize: raw.page_size };
  },
  async summary(): Promise<AdminSummary> {
    const raw = await request<Raw>("users/summary");
    return {
      accountsTotal: raw.accounts_total, accountsActive30Days: raw.accounts_active_30_days,
      accountsByRole: raw.accounts_by_role, publishersWithAccounts: raw.publishers_with_accounts,
      openInvitations: raw.open_invitations, blocked: raw.blocked,
      mostFrequentBlockReason: raw.most_frequent_block_reason,
    };
  },
  async publishers(): Promise<Publisher[]> {
    const raw = await request<Raw[]>("publishers");
    return raw.map((p) => ({ id: p.id, name: p.name }));
  },
  async createPublisher(name: string): Promise<Publisher> {
    const raw = await request<Raw>("publishers", { method: "POST", ...json({ name }) });
    return { id: raw.id, name: raw.name };
  },
  async checkInvitation(email: string): Promise<InvitationCheck> {
    const raw = await request<Raw>(`invitations/check?email=${encodeURIComponent(email)}`);
    return {
      existingAccount: raw.existing_account, verified: raw.verified, blocked: raw.blocked,
      openInvitation: raw.open_invitation,
    };
  },
  async invite(input: InviteInput): Promise<{ emailSent: boolean }> {
    const raw = await request<Raw>("invitations", {
      method: "POST",
      ...json({
        email: input.email, role: input.role, publisher_id: input.publisherId,
        locale: input.locale, message: input.message.trim() || null,
      }),
    });
    return { emailSent: raw.email_sent };
  },
  async resendInvitation(id: string): Promise<{ emailSent: boolean }> {
    const raw = await request<Raw>(`invitations/${id}/resend`, { method: "POST" });
    return { emailSent: raw.email_sent };
  },
  withdrawInvitation: (id: string) => request<void>(`invitations/${id}`, { method: "DELETE" }),
  downgradeToUser: (id: string) =>
    request<void>(`accounts/${id}`, { method: "PATCH", ...json({ role: "user" }) }),
  changePublisher: (id: string, publisherId: string) =>
    request<void>(`accounts/${id}`, { method: "PATCH", ...json({ publisher_id: publisherId }) }),
  async block(id: string, reason: BlockReason): Promise<{ emailSent: boolean }> {
    const raw = await request<Raw>(`accounts/${id}/block`, { method: "POST", ...json({ reason }) });
    return { emailSent: raw.email_sent };
  },
  unblock: (id: string) => request<void>(`accounts/${id}/unblock`, { method: "POST" }),
  async remove(id: string, confirmEmail: string): Promise<{ emailSent: boolean }> {
    const raw = await request<Raw>(`accounts/${id}`, {
      method: "DELETE", ...json({ confirm_email: confirmEmail }),
    });
    return { emailSent: raw.email_sent };
  },
  roleMatrix: () => request<RoleMatrix>("role-matrix"),
};
