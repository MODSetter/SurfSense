import { intl } from "@/i18n/intl"

// English mirrors `_required()` in modules/artifacts/service.py, whose
// `_required_code()` builds these codes; the backend's own text stays the
// fallback for a code that has no line here.
const unavailableText: Record<string, () => string> = {
  needs_chat: () =>
    intl.formatMessage({
      id: "studio_format_unavailable_chat_tooltip",
      defaultMessage: "Needs a chat model.",
    }),
  needs_image: () =>
    intl.formatMessage({
      id: "studio_format_unavailable_image_tooltip",
      defaultMessage: "Needs an image model.",
    }),
  needs_audio: () =>
    intl.formatMessage({
      id: "studio_format_unavailable_audio_tooltip",
      defaultMessage: "Needs an audio model.",
    }),
  needs_chat_image: () =>
    intl.formatMessage({
      id: "studio_format_unavailable_chat_image_tooltip",
      defaultMessage: "Needs a chat model and an image model.",
    }),
  needs_chat_audio: () =>
    intl.formatMessage({
      id: "studio_format_unavailable_chat_audio_tooltip",
      defaultMessage: "Needs a chat model and an audio model.",
    }),
}

/** The interface's own line for a reason code, or null for one it does not know. */
export function translatedUnavailable(code: string | null | undefined) {
  if (code == null || !Object.hasOwn(unavailableText, code)) return null
  return unavailableText[code]()
}
