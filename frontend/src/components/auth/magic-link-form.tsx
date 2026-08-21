// frontend/src/components/auth/magic-link-form.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

export function MagicLinkForm() {
  const { t } = useTranslation();
  const [email, setEmail] = React.useState("");
  const [sent, setSent] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await fetch("/api/auth/magic-link/request", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email }),
      });
      // Enumeration-safe by design (accounts/'s own endpoint returns the
      // identical response for a known or unknown address) -- always show
      // the same "check your inbox" confirmation, never an error branch.
      setSent(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (sent) {
    return <p className="text-sm">{t("auth.magicLinkButton")} ✓</p>;
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
      <Button type="submit" disabled={isSubmitting}>
        {t("auth.magicLinkButton")}
      </Button>
    </form>
  );
}
