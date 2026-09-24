import type en from "../../../../frontend/translations/en.json"

// FormatJS's own typing hook: a message id outside en.json is a type error.
declare global {
  namespace FormatjsIntl {
    interface Message {
      ids: keyof typeof en
    }
  }
}
