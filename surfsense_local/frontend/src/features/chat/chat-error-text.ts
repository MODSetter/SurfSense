import { intl } from "@/i18n/intl"

import type { ChatErrorKind } from "./sse"

// English mirrors modules/chat/errors.py; the backend's own text stays the fallback.
const chatErrorText: Record<ChatErrorKind, () => string> = {
  provider_auth: () =>
    intl.formatMessage({
      id: "chat_error_provider_auth",
      defaultMessage: "Your model connection needs a new API key.",
    }),
  provider_not_found: () =>
    intl.formatMessage({
      id: "chat_error_provider_not_found",
      defaultMessage:
        "The selected model couldn’t be found — pick another in Model setup.",
    }),
  provider_rate_limited: () =>
    intl.formatMessage({
      id: "chat_error_provider_rate_limited",
      defaultMessage:
        "The model provider is rate-limiting requests right now. Try again in a moment.",
    }),
  provider_unavailable: () =>
    intl.formatMessage({
      id: "chat_error_provider_unavailable",
      defaultMessage:
        "The model provider is temporarily unavailable. Try again shortly.",
    }),
  model_cannot_run: () =>
    intl.formatMessage({
      id: "chat_error_model_cannot_run",
      defaultMessage: "SurfSense cannot run this model. Pick another model.",
    }),
  context_too_long: () =>
    intl.formatMessage({
      id: "chat_error_context_too_long",
      defaultMessage:
        "This conversation is too long for the model’s context window. Start a new chat or pick a model with a larger window.",
    }),
  network: () =>
    intl.formatMessage({
      id: "chat_error_network",
      defaultMessage:
        "Couldn’t reach the model provider — check the connection’s URL in Model setup.",
    }),
  timeout: () =>
    intl.formatMessage({
      id: "chat_error_timeout",
      defaultMessage: "The model took too long to respond. Try again.",
    }),
  unknown: () =>
    intl.formatMessage({
      id: "chat_error_unknown",
      defaultMessage: "Something went wrong generating a reply. Try again.",
    }),
}

// The backend words `network` differently for the local runtime, which has no Model setup fix.
const LOCAL_RUNTIME = "llamacpp"

export function translatedChatError(error: {
  kind: string
  message: string
  provider: string
}): string {
  if (error.kind === "network" && error.provider === LOCAL_RUNTIME) {
    return intl.formatMessage({
      id: "chat_error_network_llamacpp",
      defaultMessage:
        "Couldn’t reach the local model runtime. Restart SurfSense to start it again.",
    })
  }
  const text = Object.hasOwn(chatErrorText, error.kind)
    ? chatErrorText[error.kind as ChatErrorKind]
    : undefined
  return text ? text() : error.message
}
