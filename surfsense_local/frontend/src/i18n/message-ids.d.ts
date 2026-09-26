import type en from "../../translations/en.json"

import type { AppLocale } from "./locales"

// FormatJS's own typing hook: a message id outside en.json is a type error.
declare global {
  namespace FormatjsIntl {
    interface Message {
      ids: keyof typeof en
    }
    interface IntlConfig {
      locale: AppLocale
    }
  }
}
