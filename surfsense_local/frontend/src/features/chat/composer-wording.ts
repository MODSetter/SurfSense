import { intl } from "@/i18n/intl"

// Shared with the startup frame's box, so it reads as the composer it becomes.

export function startPlaceholder() {
  return intl.formatMessage({
    id: "chat_composer_start_placeholder",
    defaultMessage: "Turn your sources into answers",
  })
}

export function messageLabel() {
  return intl.formatMessage({
    id: "chat_composer_message_aria",
    defaultMessage: "Message",
  })
}
