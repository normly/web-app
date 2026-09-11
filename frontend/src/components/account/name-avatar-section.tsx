// frontend/src/components/account/name-avatar-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Avatar } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";
import type { AccountSummary } from "@/lib/account-response";

export function NameAvatarSection({
  account, onAccountUpdated, avatarVersion, onAvatarChange,
}: {
  account: AccountSummary;
  onAccountUpdated: (account: AccountSummary) => void;
  avatarVersion: number;
  onAvatarChange: () => void;
}) {
  const { t } = useTranslation();
  const [firstName, setFirstName] = React.useState(account.firstName ?? "");
  const [lastName, setLastName] = React.useState(account.lastName ?? "");
  const [isSavingName, setIsSavingName] = React.useState(false);
  const [isUpdatingAvatar, setIsUpdatingAvatar] = React.useState(false);
  const [nameStatus, setNameStatus] = React.useState<"idle" | "error">("idle");
  const [avatarStatus, setAvatarStatus] = React.useState<"idle" | "error">("idle");

  const saveName = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSavingName(true);
    try {
      const response = await fetch("/api/account/profile", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ first_name: firstName || null, last_name: lastName || null }),
      });
      if (response.ok) {
        setNameStatus("idle");
        onAccountUpdated(await response.json());
      } else {
        setNameStatus("error");
      }
    } catch {
      setNameStatus("error");
    } finally {
      setIsSavingName(false);
    }
  };

  const uploadAvatar = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsUpdatingAvatar(true);
    try {
      const formData = new FormData();
      formData.append("avatar", file);
      const response = await fetch("/api/account/avatar", { method: "POST", body: formData });
      if (response.ok) {
        setAvatarStatus("idle");
        onAccountUpdated(await response.json());
        onAvatarChange();
      } else {
        setAvatarStatus("error");
      }
    } catch {
      setAvatarStatus("error");
    } finally {
      setIsUpdatingAvatar(false);
      event.target.value = "";
    }
  };

  const removeAvatar = async () => {
    setIsUpdatingAvatar(true);
    try {
      const response = await fetch("/api/account/avatar", { method: "DELETE" });
      if (response.ok) {
        setAvatarStatus("idle");
        onAccountUpdated(await response.json());
        onAvatarChange();
      } else {
        setAvatarStatus("error");
      }
    } catch {
      setAvatarStatus("error");
    } finally {
      setIsUpdatingAvatar(false);
    }
  };

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">{t("account.nameAvatarTitle")}</h2>
      <div className="flex items-center gap-4">
        <Avatar
          key={avatarVersion} avatarVersion={avatarVersion} hasAvatar={account.hasAvatar}
          firstName={account.firstName} lastName={account.lastName} email={account.email}
          size={64}
        />
        <div className="flex flex-col gap-2">
          <label className="text-sm underline">
            {t("account.uploadAvatarButton")}
            <input
              type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
              onChange={uploadAvatar} disabled={isUpdatingAvatar}
            />
          </label>
          {account.hasAvatar && (
            <button
              type="button" className="text-sm text-destructive underline"
              onClick={removeAvatar} disabled={isUpdatingAvatar}
            >
              {t("account.removeAvatarButton")}
            </button>
          )}
          {avatarStatus === "error" && (
            <p className="text-sm text-destructive">{t("account.avatarUpdateError")}</p>
          )}
        </div>
      </div>
      <form onSubmit={saveName} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          {t("account.firstNameLabel")}
          <Input value={firstName} onChange={(event) => setFirstName(event.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("account.lastNameLabel")}
          <Input value={lastName} onChange={(event) => setLastName(event.target.value)} />
        </label>
        {nameStatus === "error" && (
          <p className="text-sm text-destructive">{t("account.saveNameError")}</p>
        )}
        <Button type="submit" disabled={isSavingName} className="self-start">
          {t("account.saveNameButton")}
        </Button>
      </form>
    </section>
  );
}
