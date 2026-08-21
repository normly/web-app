// frontend/src/lib/i18n/dictionary-keys.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import de from "./de.json";

// Derives the set of valid "chat.sendButton"-style dotted paths straight
// from the German dictionary's shape, so t("chat.sendbutton") (a typo) is
// a compile error instead of a silent missing-key bug.
type Join<K extends string, P extends string> = P extends "" ? K : `${K}.${P}`;

type DictionaryPaths<T> = {
  [K in keyof T & string]: T[K] extends object ? Join<K, DictionaryPaths<T[K]>> : K;
}[keyof T & string];

export type TranslationKey = DictionaryPaths<typeof de>;
