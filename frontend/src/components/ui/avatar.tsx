// frontend/src/components/ui/avatar.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";

function initialsFor(
  firstName: string | null, lastName: string | null, email: string,
): string {
  if (firstName && lastName) return `${firstName[0]}${lastName[0]}`.toUpperCase();
  if (firstName) return firstName[0].toUpperCase();
  if (lastName) return lastName[0].toUpperCase();
  return (email[0] ?? "?").toUpperCase();
}

export function Avatar({
  avatarVersion = 0, firstName, lastName, email, size = 32,
}: {
  avatarVersion?: number;
  firstName: string | null;
  lastName: string | null;
  email: string;
  size?: number;
}) {
  const [imageFailed, setImageFailed] = React.useState(false);

  if (!imageFailed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- this is a
      // same-origin BFF route (/api/account/avatar), not a remote URL
      // next/image's optimizer could help with, and the avatarVersion query
      // param changes on every upload/removal, which next/image handles
      // awkwardly for a URL that intentionally varies per session.
      //
      // alt is a real, non-empty string on purpose: alt="" gives the <img>
      // an implicit ARIA role of "presentation" instead of "img", which
      // both real screen readers and getByRole("img") in tests would then
      // skip entirely.
      //
      // onError covers both "no avatar set" (backend 404) and any other
      // fetch failure -- both cases fall back to the same initials display
      // this component already used before this endpoint existed.
      <img
        key={avatarVersion}
        src={
          avatarVersion === 0 ? "/api/account/avatar" : `/api/account/avatar?v=${avatarVersion}`
        }
        alt="Profilbild" className="rounded-full object-cover"
        style={{ width: size, height: size }}
        onError={() => setImageFailed(true)}
      />
    );
  }
  return (
    <span
      className="flex items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium"
      style={{ width: size, height: size }}
    >
      {initialsFor(firstName, lastName, email)}
    </span>
  );
}
