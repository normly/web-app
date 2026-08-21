// frontend/src/components/auth/auth-dialog.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";
import { LoginForm } from "@/components/auth/login-form";
import { RegisterForm } from "@/components/auth/register-form";
import { MagicLinkForm } from "@/components/auth/magic-link-form";

export function AuthDialog({ onAuthenticated }: { onAuthenticated: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = React.useState(false);

  const handleSuccess = () => {
    setOpen(false);
    onAuthenticated();
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">{t("auth.loginTab")}</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>{t("auth.loginTab")}</DialogTitle>
        <Tabs defaultValue="login">
          <TabsList>
            <TabsTrigger value="login">{t("auth.loginTab")}</TabsTrigger>
            <TabsTrigger value="register">{t("auth.registerTab")}</TabsTrigger>
            <TabsTrigger value="magic-link">{t("auth.magicLinkTab")}</TabsTrigger>
          </TabsList>
          <TabsContent value="login">
            <LoginForm onSuccess={handleSuccess} />
          </TabsContent>
          <TabsContent value="register">
            <RegisterForm onSuccess={handleSuccess} />
          </TabsContent>
          <TabsContent value="magic-link">
            <MagicLinkForm />
          </TabsContent>
        </Tabs>
        <a href="/api/auth/google/login" className="text-center text-sm underline">
          {t("auth.googleButton")}
        </a>
      </DialogContent>
    </Dialog>
  );
}
