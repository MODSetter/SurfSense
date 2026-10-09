import { intl } from "@/i18n/intl"

import type { LocalRow } from "./api"

// The codes are `NotRunnableCode` in the backend's
// modules/llm/catalog/local/classifier.py; keep the two in sync. English
// mirrors that module's sentences, which stay the fallback for a code with no
// line here.
const notRunnableText: Record<string, () => string> = {
  embedder: () =>
    intl.formatMessage({
      id: "models_not_runnable_embedder_body",
      defaultMessage:
        "This model turns text into numbers for search. It cannot answer questions, and SurfSense already has its own.",
    }),
  speech_out: () =>
    intl.formatMessage({
      id: "models_not_runnable_speech_out_body",
      defaultMessage:
        "This model reads text aloud. SurfSense cannot run speech models yet.",
    }),
  speech_in: () =>
    intl.formatMessage({
      id: "models_not_runnable_speech_in_body",
      defaultMessage:
        "This model writes down what it hears in audio. It cannot answer questions.",
    }),
  audio_cpp: () =>
    intl.formatMessage({
      id: "models_not_runnable_audio_cpp_body",
      defaultMessage:
        "This model runs on audio.cpp. SurfSense runs only the voices in its list.",
    }),
  labeller: () =>
    intl.formatMessage({
      id: "models_not_runnable_labeller_body",
      defaultMessage:
        "This model puts labels on things. It cannot hold a conversation.",
    }),
  ocr: () =>
    intl.formatMessage({
      id: "models_not_runnable_ocr_body",
      defaultMessage:
        "This model reads text out of images in one pass. It cannot hold a conversation.",
    }),
  drafter: () =>
    intl.formatMessage({
      id: "models_not_runnable_drafter_body",
      defaultMessage:
        "This file makes another model faster. It cannot answer on its own.",
    }),
  projector: () =>
    intl.formatMessage({
      id: "models_not_runnable_projector_body",
      defaultMessage:
        "This is the vision half of another model. Install the model it belongs to instead.",
    }),
  not_weights: () =>
    intl.formatMessage({
      id: "models_not_runnable_not_weights_body",
      defaultMessage:
        "This file steers another model. It is not a model on its own.",
    }),
  image: () =>
    intl.formatMessage({
      id: "models_not_runnable_image_body",
      defaultMessage:
        "This model makes pictures. SurfSense cannot run it from search yet.",
    }),
  image_edit: () =>
    intl.formatMessage({
      id: "models_not_runnable_image_edit_body",
      defaultMessage:
        "This model edits pictures. SurfSense cannot run picture editing yet.",
    }),
  video: () =>
    intl.formatMessage({
      id: "models_not_runnable_video_body",
      defaultMessage:
        "This model makes video. SurfSense cannot run video models yet.",
    }),
  unsupported: () =>
    intl.formatMessage({
      id: "models_not_runnable_unsupported_body",
      defaultMessage: "SurfSense cannot run this model.",
    }),
}

/** The interface's own line for a code it knows, or null. */
export function notRunnableLine(
  code: string | null | undefined
): string | null {
  return code != null && Object.hasOwn(notRunnableText, code)
    ? notRunnableText[code]()
    : null
}

/**
 * Why a row cannot run: the interface's line for its code, or the backend's
 * sentence for a reason that has none. Null for a row that runs.
 */
export function notRunnableReason(
  row: Pick<LocalRow, "not_runnable_code" | "not_runnable_reason">
): string | null {
  return notRunnableLine(row.not_runnable_code) ?? row.not_runnable_reason
}
