// frontend/tests/unit/i18n.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LocaleProvider, useTranslation } from "@/lib/i18n/provider";
import de from "@/lib/i18n/de.json";
import en from "@/lib/i18n/en.json";

function Probe() {
  const { t } = useTranslation();
  return <span>{t("chat.sendButton")}</span>;
}

function Switch() {
  const { setLocale } = useTranslation();
  return <button onClick={() => setLocale("en")}>switch</button>;
}

describe("i18n", () => {
  it("renders the German string by default", () => {
    render(
      <LocaleProvider initialLocale="de">
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByText(de.chat.sendButton)).toBeInTheDocument();
  });

  it("renders the English string when initialised with locale=en", () => {
    render(
      <LocaleProvider initialLocale="en">
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByText(en.chat.sendButton)).toBeInTheDocument();
  });

  it("has an identical key structure in both dictionaries", () => {
    const flatten = (obj: object, prefix = ""): string[] =>
      Object.entries(obj).flatMap(([key, value]) =>
        typeof value === "object" && value !== null
          ? flatten(value, `${prefix}${key}.`)
          : [`${prefix}${key}`],
      );
    expect(flatten(de).sort()).toEqual(flatten(en).sort());
  });

  it("stores the new locale on the account when switching", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    render(
      <LocaleProvider initialLocale="de">
        <Switch />
      </LocaleProvider>,
    );

    await act(async () => screen.getByText("switch").click());

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/account/locale",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ locale: "en" }) }),
    );
    vi.unstubAllGlobals();
  });
});
