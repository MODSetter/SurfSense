import { intl } from "@/i18n/intl"

import type { ChatErrorKind } from "./sse"

// English mirrors modules/chat/errors.py; the backend's own text stays the fallback.
const chatErrorText: Record<ChatErrorKind, () => string> = {
  provider_auth: () => intl.formatMessage({ id: "chat_error_provider_auth" }),
  provider_not_found: () =>
    intl.formatMessage({ id: "chat_error_provider_not_found" }),
  provider_rate_limited: () =>
    intl.formatMessage({ id: "chat_error_provider_rate_limited" }),
  provider_unavailable: () =>
    intl.formatMessage({ id: "chat_error_provider_unavailable" }),
  model_cannot_run: () =>
    intl.formatMessage({ id: "chat_error_model_cannot_run" }),
  context_too_long: () =>
    intl.formatMessage({ id: "chat_error_context_too_long" }),
  network: () => intl.formatMessage({ id: "chat_error_network" }),
  timeout: () => intl.formatMessage({ id: "chat_error_timeout" }),
  unknown: () => intl.formatMessage({ id: "chat_error_unknown" }),
}

// The backend words `network` differently for the local runtime, which has no Model setup fix.
const LOCAL_RUNTIME = "llamacpp"

export function translatedChatError(error: {
  kind: string
  message: string
  provider: string
}): string {
  if (error.kind === "network" && error.provider === LOCAL_RUNTIME) {
    return intl.formatMessage({ id: "chat_error_network_llamacpp" })
  }
  const text = Object.hasOwn(chatErrorText, error.kind)
    ? chatErrorText[error.kind as ChatErrorKind]
    : undefined
  return text ? text() : error.message
}
