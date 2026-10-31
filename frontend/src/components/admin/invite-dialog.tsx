// frontend/src/components/admin/invite-dialog.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import {
  ROLES, adminApi, errorKey, type InvitationCheck, type Publisher, type Role,
} from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n/provider";
import { interpolate } from "@/lib/i18n/interpolate";

const NEW_PUBLISHER = "__new__";
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function InviteDialog({ onClose, onDone }: { onClose: () => void; onDone: (text: string) => void }) {
  const { t, locale } = useTranslation();
  const [email, setEmail] = React.useState("");
  const [role, setRole] = React.useState<Role>("user");
  const [publishers, setPublishers] = React.useState<Publisher[]>([]);
  const [publisherId, setPublisherId] = React.useState("");
  const [newName, setNewName] = React.useState("");
  const [language, setLanguage] = React.useState<"de" | "en">(locale);
  const [message, setMessage] = React.useState("");
  const [check, setCheck] = React.useState<InvitationCheck | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (role !== "publisher" || publishers.length) return;
    adminApi.publishers().then(setPublishers).catch(() => setPublishers([]));
  }, [role, publishers.length]);

  async function runCheck() {
    if (!EMAIL_PATTERN.test(email.trim())) {
      setCheck(null);
      return;
    }
    try {
      setCheck(await adminApi.checkInvitation(email.trim()));
    } catch {
      setCheck(null);
    }
  }

  async function addPublisher() {
    setError(null);
    try {
      const created = await adminApi.createPublisher(newName.trim());
      setPublishers((list) => [...list, created].sort((a, b) => a.name.localeCompare(b.name)));
      setPublisherId(created.id);
      setNewName("");
    } catch (failure) {
      setError(t(errorKey(failure)));
    }
  }

  const needsPublisher = role === "publisher";
  const canSend = EMAIL_PATTERN.test(email.trim())
    && (!needsPublisher || (publisherId !== "" && publisherId !== NEW_PUBLISHER))
    && !check?.blocked && message.length <= 500 && !busy;

  async function send() {
    setBusy(true);
    setError(null);
    try {
      const { emailSent } = await adminApi.invite({
        email: email.trim(), role, publisherId: needsPublisher ? publisherId : null,
        locale: language, message,
      });
      onDone(emailSent
        ? interpolate(t("admin.notices.invited"), { email: email.trim() })
        : t("admin.notices.emailNotSent"));
    } catch (failure) {
      setError(t(errorKey(failure)));
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogTitle>{t("admin.invite.title")}</DialogTitle>
        <div className="mt-4 grid gap-4 md:grid-cols-[2fr_1fr_1fr]">
          <label className="flex flex-col gap-2 text-sm">
            {t("admin.invite.email")}
            <Input type="email" required placeholder={t("admin.invite.emailPlaceholder")} value={email}
                   onChange={(event) => { setEmail(event.target.value); setCheck(null); }}
                   onBlur={runCheck} />
          </label>
          <label className="flex flex-col gap-2 text-sm">
            {t("admin.invite.role")}
            <NativeSelect value={role} onChange={(event) => setRole(event.target.value as Role)}>
              {ROLES.map((r) => <option key={r} value={r}>{t(`admin.roles.${r}`)}</option>)}
            </NativeSelect>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            {t("admin.invite.language")}
            <NativeSelect value={language} onChange={(event) => setLanguage(event.target.value as "de" | "en")}>
              <option value="de">{t("admin.invite.languageDe")}</option>
              <option value="en">{t("admin.invite.languageEn")}</option>
            </NativeSelect>
          </label>
        </div>
        {needsPublisher && (
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm">
              {t("admin.invite.publisher")}
              <NativeSelect value={publisherId} onChange={(event) => setPublisherId(event.target.value)}>
                <option value="" disabled>{t("admin.invite.publisherPlaceholder")}</option>
                {publishers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                <option value={NEW_PUBLISHER}>{t("admin.invite.newPublisher")}</option>
              </NativeSelect>
            </label>
            {publisherId === NEW_PUBLISHER && (
              <div className="flex items-end gap-2">
                <label className="flex flex-1 flex-col gap-2 text-sm">
                  {t("admin.invite.newPublisherName")}
                  <Input value={newName} onChange={(event) => setNewName(event.target.value)} />
                </label>
                <Button variant="outline" disabled={!newName.trim()} onClick={addPublisher}>
                  {t("admin.invite.addPublisher")}
                </Button>
              </div>
            )}
          </div>
        )}
        <label className="mt-4 flex flex-col gap-2 text-sm">
          {t("admin.invite.message")}
          <Textarea maxLength={500} placeholder={t("admin.invite.messagePlaceholder")} value={message}
                    onChange={(event) => setMessage(event.target.value)} />
        </label>
        {check?.blocked && <p role="alert" className="mt-3 text-sm text-destructive">{t("admin.invite.blockedAccount")}</p>}
        {check && !check.blocked && check.existingAccount && (
          <p className="mt-3 text-sm">
            {check.verified ? t("admin.invite.existingAccount") : t("admin.invite.unverifiedAccount")}
          </p>
        )}
        {check?.openInvitation && <p className="mt-2 text-sm">{t("admin.invite.openInvitation")}</p>}
        <p className="mt-3 text-sm text-muted-foreground">{t("admin.invite.help")}</p>
        {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
        <div className="mt-6 flex justify-start gap-2">
          <Button disabled={!canSend} onClick={send}>{t("admin.invite.send")}</Button>
          <Button variant="outline" onClick={onClose}>{t("admin.invite.cancel")}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
