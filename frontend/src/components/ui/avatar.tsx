// frontend/src/components/ui/avatar.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

function initialsFor(
  firstName: string | null, lastName: string | null, email: string,
): string {
  if (firstName && lastName) return `${firstName[0]}${lastName[0]}`.toUpperCase();
  if (firstName) return firstName[0].toUpperCase();
  if (lastName) return lastName[0].toUpperCase();
  return (email[0] ?? "?").toUpperCase();
}

export function Avatar({
  avatarDataUrl, firstName, lastName, email, size = 32,
}: {
  avatarDataUrl: string | null;
  firstName: string | null;
  lastName: string | null;
  email: string;
  size?: number;
}) {
  if (avatarDataUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- avatarDataUrl
      // is a data: URI, not a remote URL next/image's optimizer could help
      // with, and it changes on every upload/removal, which next/image
      // handles awkwardly for user-controlled data URIs.
      //
      // alt is a real, non-empty string on purpose: alt="" gives the <img>
      // an implicit ARIA role of "presentation" instead of "img", which
      // both real screen readers and getByRole("img") in tests would then
      // skip entirely.
      <img
        src={avatarDataUrl} alt="Profilbild" className="rounded-full object-cover"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span
      className="flex items-center justify-center rounded-full bg-brand text-brand-foreground text-xs font-medium"
      style={{ width: size, height: size }}
    >
      {initialsFor(firstName, lastName, email)}
    </span>
  );
}
