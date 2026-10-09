import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

// English mirrors `_required()` in modules/artifacts/service.py, whose
// `_required_code()` builds these codes for a refused create or regenerate
// (a refine's `needs_chat` comes from studio_documents/fits.py);
// the backend's own text stays the fallback for a code that has no line here.
const studioErrorText: Record<string, () => string> = {
  needs_chat: () =>
    intl.formatMessage({
      id: "studio_error_needs_chat",
      defaultMessage: "Needs a chat model.",
    }),
  needs_image: () =>
    intl.formatMessage({
      id: "studio_error_needs_image",
      defaultMessage: "Needs an image model.",
    }),
  needs_audio: () =>
    intl.formatMessage({
      id: "studio_error_needs_audio",
      defaultMessage: "Needs an audio model.",
    }),
  needs_chat_image: () =>
    intl.formatMessage({
      id: "studio_error_needs_chat_image",
      defaultMessage: "Needs a chat model and an image model.",
    }),
  needs_chat_audio: () =>
    intl.formatMessage({
      id: "studio_error_needs_chat_audio",
      defaultMessage: "Needs a chat model and an audio model.",
    }),
}

/** The interface's own line for a refused Studio action, or null for an error it has none for. */
export function translatedStudioError(error: unknown) {
  if (
    !(error instanceof ApiError) ||
    error.code === null ||
    !Object.hasOwn(studioErrorText, error.code)
  ) {
    return null
  }
  return studioErrorText[error.code]()
}
