import { useEffect, useState, type ComponentProps } from "react"

import { Select } from "@/components/ui/select"
import { SELECTABLE_LOCALES, type LocalePreference } from "@/i18n/locales"
import { intl } from "@/i18n/intl"
import { localeSource } from "@/i18n/locale-source"

// Each language in its own name, so a user in the wrong one can still find theirs.
function nativeName(locale: string): string {
  return (
    new Intl.DisplayNames([locale], { type: "language" }).of(locale) ?? locale
  )
}

export function LanguageSelect(
  props: Omit<ComponentProps<typeof Select>, "value" | "onChange">
) {
  const [preference, setPreference] = useState<LocalePreference>("system")

  useEffect(() => {
    let active = true
    void localeSource()
      .preference()
      .then((saved) => {
        if (active) setPreference(saved as LocalePreference)
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <Select
      {...props}
      value={preference}
      onChange={(event) => {
        const next = event.target.value as LocalePreference
        setPreference(next)
        void localeSource().set(next)
      }}
    >
      <option value="system">
        {intl.formatMessage({
          id: "settings_general_language_system_label",
          defaultMessage: "Match system",
        })}
      </option>
      {SELECTABLE_LOCALES.map((locale) => (
        <option key={locale} value={locale}>
          {nativeName(locale)}
        </option>
      ))}
    </Select>
  )
}
