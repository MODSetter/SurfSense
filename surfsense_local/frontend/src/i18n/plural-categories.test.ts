import { describe, expect, it } from "vitest"
import type { MessageFormatElement } from "react-intl"

import { LOCALES, type Locale } from "./locales"

// Every shipped language, from the same glob intl.ts uses, so a language added
// to LOCALES is covered here without editing this file — and one added without
// a catalog fails instead of going unchecked.
const compiled = import.meta.glob<Record<string, MessageFormatElement[]>>(
  ["./compiled/*.json", "!./compiled/en-XA.json"],
  { eager: true, import: "default" }
)

// TYPE.plural and TYPE.tag in @formatjs/icu-messageformat-parser.
const PLURAL = 6
const TAG = 8

type Catalog = Record<string, MessageFormatElement[]>

function pluralCategoryMismatches(catalog: Catalog, locale: Locale): string[] {
  const problems: string[] = []
  const expected = {
    cardinal: new Intl.PluralRules(locale).resolvedOptions().pluralCategories,
    ordinal: new Intl.PluralRules(locale, { type: "ordinal" }).resolvedOptions()
      .pluralCategories,
  }
  const walk = (id: string, elements: MessageFormatElement[]) => {
    for (const element of elements) {
      if (element.type === PLURAL) {
        const wanted = [...expected[element.pluralType ?? "cardinal"]]
          .sort()
          .join()
        // `=0`-style exact matches sit on top of the categories, never instead of them.
        const written = Object.keys(element.options)
          .filter((key) => !key.startsWith("="))
          .sort()
          .join()
        if (written !== wanted)
          problems.push(`${id}: has ${written}, needs ${wanted}`)
      }
      if (element.type === TAG) walk(id, element.children)
      if ("options" in element) {
        for (const option of Object.values(element.options))
          walk(id, option.value)
      }
    }
  }
  for (const [id, elements] of Object.entries(catalog)) walk(id, elements)
  return problems
}

describe("plural categories", () => {
  it.each(LOCALES)(
    "%s writes exactly the plural forms its language has",
    (locale) => {
      const catalog = compiled[`./compiled/${locale}.json`]
      expect(catalog, `no compiled catalog for ${locale}`).toBeDefined()
      expect(pluralCategoryMismatches(catalog as Catalog, locale)).toEqual([])
    }
  )

  it("flags a German plural that lost its singular", () => {
    const broken = {
      demo_label: [
        {
          type: PLURAL,
          value: "count",
          pluralType: "cardinal",
          offset: 0,
          options: { other: { value: [] } },
        },
      ],
    } as unknown as Catalog
    expect(pluralCategoryMismatches(broken, "de")).toEqual([
      "demo_label: has other, needs one,other",
    ])
  })
})
