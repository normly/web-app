// frontend/src/components/admin/badges.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { Ban, BookOpen, CircleCheck, Clock, Hourglass, Shield, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Role, UserStatus } from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

const ROLE_ICON = { administrator: Shield, publisher: BookOpen, user: User } as const;

export function RoleBadge({ role }: { role: Role }) {
  const { t } = useTranslation();
  const Icon = ROLE_ICON[role];
  return (
    <Badge variant={role === "administrator" ? "default" : role === "publisher" ? "secondary" : "outline"}
           className="gap-1 whitespace-nowrap">
      <Icon className="size-3" aria-hidden />
      {t(`admin.roles.${role}`)}
    </Badge>
  );
}

const STATUS_STYLE: Record<UserStatus, { icon: typeof Clock; className: string }> = {
  active: { icon: CircleCheck, className: "border-green-600/40 text-green-700 dark:text-green-400" },
  invited: { icon: Clock, className: "border-amber-600/40 text-amber-700 dark:text-amber-400" },
  expired: { icon: Hourglass, className: "border-border text-muted-foreground" },
  blocked: { icon: Ban, className: "border-red-600/40 text-red-700 dark:text-red-400" },
};

export function StatusBadge({ status }: { status: UserStatus }) {
  const { t } = useTranslation();
  const { icon: Icon, className } = STATUS_STYLE[status];
  return (
    <Badge variant="outline" className={cn("gap-1 whitespace-nowrap", className)}>
      <Icon className="size-3" aria-hidden />
      {t(`admin.status.${status}`)}
    </Badge>
  );
}
