// frontend/src/components/app-shell.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronsUpDown, LogOut, MessageSquare, Search, User as UserIcon } from "lucide-react";
import { ProfileOverlay } from "@/components/account/profile-overlay";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
} from "@/components/ui/sidebar";
import { useTranslation } from "@/lib/i18n/provider";
import { useAccountSession } from "@/lib/use-account-session";
import type { AccountSummary } from "@/lib/account-response";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

const NAV_ITEMS: Array<{ href: string; labelKey: TranslationKey; icon: typeof MessageSquare }> = [
  { href: "/", labelKey: "nav.chat", icon: MessageSquare },
  { href: "/search", labelKey: "nav.search", icon: Search },
];

function NavUser({
  account,
  avatarVersion,
  logout,
  onOpenProfile,
}: {
  account: AccountSummary | null;
  avatarVersion: number;
  logout: () => Promise<void>;
  onOpenProfile: () => void;
}) {
  const { t } = useTranslation();

  if (!account) {
    return (
      <div className="p-2 group-data-[collapsible=icon]:hidden">
        <Button variant="outline" asChild>
          <Link href="/login">{t("auth.loginTab")}</Link>
        </Button>
      </div>
    );
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg">
              <Avatar
                key={avatarVersion}
                avatarVersion={avatarVersion}
                firstName={account.firstName}
                lastName={account.lastName}
                email={account.email}
              />
              <span className="truncate text-sm text-muted-foreground">{account.email}</span>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          {/* Fixed min-w-56 instead of matching the trigger's width: the
              canonical block uses Tailwind v4's `w-(--radix-...)` bare
              arbitrary-property shorthand, invalid syntax under this
              project's Tailwind v3 (silently dropped, same as the
              opacity-modifier trap -- see Global Constraints). */}
          <DropdownMenuContent className="min-w-56 rounded-lg" side="top" align="end">
            <DropdownMenuLabel className="font-normal">{account.email}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onOpenProfile}>
              <UserIcon className="mr-2 size-4" />
              {t("nav.account")}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout}>
              <LogOut className="mr-2 size-4" />
              {t("auth.logoutButton")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}

export function AppShell({
  instanceName,
  logoPath,
  children,
}: {
  instanceName: string;
  logoPath: string | null;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { t } = useTranslation();
  const [profileOpen, setProfileOpen] = React.useState(false);
  const [avatarVersion, setAvatarVersion] = React.useState(0);
  const { account, logout, setAccount } = useAccountSession();

  return (
    <SidebarProvider>
      <Sidebar variant="inset" collapsible="icon">
        <SidebarHeader>
          <div className="flex items-center gap-2 px-2 py-1">
            {logoPath ? (
              <img
                src={logoPath}
                alt={instanceName}
                className="h-6 group-data-[collapsible=icon]:hidden"
              />
            ) : (
              <span className="truncate font-semibold group-data-[collapsible=icon]:hidden">
                {instanceName}
              </span>
            )}
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {NAV_ITEMS.map(({ href, labelKey, icon: Icon }) => (
                  <SidebarMenuItem key={href}>
                    <SidebarMenuButton asChild isActive={pathname === href} tooltip={t(labelKey)}>
                      <Link href={href}>
                        <Icon className="size-4" />
                        <span>{t(labelKey)}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter>
          <NavUser
            account={account}
            avatarVersion={avatarVersion}
            logout={logout}
            onOpenProfile={() => setProfileOpen(true)}
          />
        </SidebarFooter>
        {/* Kept for desktop drag-to-toggle at the sidebar edge; the reachable
            control for keyboard/touch users is PageHeader's SidebarTrigger
            (see Finding 1 in the app-shell final review). */}
        <SidebarRail aria-label={t("nav.toggleSidebar")} />
      </Sidebar>
      <SidebarInset>{children}</SidebarInset>
      <ProfileOverlay
        open={profileOpen}
        onOpenChange={setProfileOpen}
        account={account}
        setAccount={setAccount}
        avatarVersion={avatarVersion}
        onAvatarChange={() => setAvatarVersion((v) => v + 1)}
      />
    </SidebarProvider>
  );
}
