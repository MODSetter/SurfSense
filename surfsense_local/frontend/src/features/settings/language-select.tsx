import { useEffect, useState, type ComponentProps } from "react"

import { Select } from "@/components/ui/select"
import { LOCALES, type LocalePreference } from "@/i18n/locales"
import { intl } from "@/i18n/intl"

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
    void window.surfsense?.locale?.preference().then((saved) => {
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
        void window.surfsense?.locale?.set(next)
      }}
    >
      <option value="system">
        {intl.formatMessage({ id: "settings_general_language_system_label" })}
      </option>
      {LOCALES.map((locale) => (
        <option key={locale} value={locale}>
          {nativeName(locale)}
        </option>
      ))}
    </Select>
  )
}
