import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

// English mirrors `_required()` in modules/artifacts/service.py, whose
// `_required_code()` builds the `needs_*` codes for a refused create or
// regenerate (a refine's `needs_chat` comes from studio_documents/fits.py),
// and the sentences `refused()` sends for a job that cannot start, be run
// again or be stopped, and for a document that cannot be refined
// (studio_documents/service.py);
// the backend's own text stays the fallback for a code that has no line here.
const studioErrorText: Record<string, () => string> = {
  already_generating: () =>
    intl.formatMessage({
      id: "studio_error_already_generating",
      defaultMessage: "Already generating.",
    }),
  nothing_running: () =>
    intl.formatMessage({
      id: "studio_error_nothing_running",
      defaultMessage: "Nothing is running.",
    }),
  no_sources: () =>
    intl.formatMessage({
      id: "studio_error_no_sources",
      defaultMessage: "Pick at least one source.",
    }),
  sources_indexing: () =>
    intl.formatMessage({
      id: "studio_error_sources_indexing",
      defaultMessage: "The chosen sources are still indexing.",
    }),
  sources_gone: () =>
    intl.formatMessage({
      id: "studio_error_sources_gone",
      defaultMessage: "None of this artifact’s sources are left.",
    }),
  not_refinable: () =>
    intl.formatMessage({
      id: "studio_error_not_refinable",
      defaultMessage:
        "Only a Word document, PDF or web page made in Studio can be refined.",
    }),
  agent_made: () =>
    intl.formatMessage({
      id: "studio_error_agent_made",
      defaultMessage:
        "The agent made this document: ask for changes in its chat.",
    }),
  version_unfinished: () =>
    intl.formatMessage({
      id: "studio_error_version_unfinished",
      defaultMessage:
        "This version did not finish: retry it, or refine another version.",
    }),
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
