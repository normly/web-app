// frontend/src/components/auth/login-form.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

export function LoginForm({ onSuccess }: { onSuccess: () => void }) {
  const { t } = useTranslation();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [showResetRequest, setShowResetRequest] = React.useState(false);
  const [resetSent, setResetSent] = React.useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(false);
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (response.ok) {
        onSuccess();
      } else {
        setError(true);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const submitResetRequest = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await fetch("/api/auth/password-reset/request", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email }),
      });
      setResetSent(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (showResetRequest) {
    if (resetSent) {
      return <p className="text-sm">{t("auth.resetLinkSent")}</p>;
    }
    return (
      <form onSubmit={submitResetRequest} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          {t("auth.emailLabel")}
          <Input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <Button type="submit" disabled={isSubmitting}>
          {t("auth.resetRequestButton")}
        </Button>
        <button
          type="button"
          className="text-sm underline"
          onClick={() => setShowResetRequest(false)}
        >
          {t("auth.backToLogin")}
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">
        {t("auth.emailLabel")}
        <Input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        {t("auth.passwordLabel")}
        <Input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
      </label>
      {error && <p className="text-sm text-red-600">{t("auth.genericError")}</p>}
      <Button type="submit" disabled={isSubmitting}>
        {t("auth.loginButton")}
      </Button>
      <button
        type="button"
        className="text-sm underline"
        onClick={() => setShowResetRequest(true)}
      >
        {t("auth.forgotPasswordLink")}
      </button>
    </form>
  );
}
