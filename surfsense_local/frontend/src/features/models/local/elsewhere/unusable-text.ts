import { intl } from "@/i18n/intl"

import { notRunnableLine } from "../chat/not-runnable-text"

// The codes are `UnusableCode` in the backend's
// modules/llm/catalog/local/engines/llamacpp/elsewhere/runs_here.py, beside the
// classifier's own (`not-runnable-text.ts`); keep them in sync. English mirrors
// that module's sentences, which stay the fallback for a code with no line here.
const unusableText: Record<string, () => string> = {
  unreadable: () =>
    intl.formatMessage({
      id: "models_elsewhere_unusable_unreadable_body",
      defaultMessage: "SurfSense cannot read this file.",
    }),
  not_a_model: () =>
    intl.formatMessage({
      id: "models_elsewhere_unusable_not_a_model_body",
      defaultMessage: "This file is part of a model, not a model on its own.",
    }),
  unknown_architecture: () =>
    intl.formatMessage({
      id: "models_elsewhere_unusable_unknown_architecture_body",
      defaultMessage:
        "This model is in a format SurfSense’s runtime cannot load.",
    }),
  vision_inside: () =>
    intl.formatMessage({
      id: "models_elsewhere_unusable_vision_inside_body",
      defaultMessage:
        "This file holds its image support inside the model, a format only the app that downloaded it can run.",
    }),
  path: () =>
    intl.formatMessage({
      id: "models_elsewhere_unusable_path_body",
      defaultMessage:
        "SurfSense cannot open a file whose folder or name contains # or ;.",
    }),
  missing_parts: () =>
    intl.formatMessage({
      id: "models_elsewhere_unusable_missing_parts_body",
      defaultMessage: "Some parts of this model are missing.",
    }),
  not_found: () =>
    intl.formatMessage({
      id: "models_elsewhere_unusable_not_found_body",
      defaultMessage: "Nothing is there any more.",
    }),
  in_models_folder: () =>
    intl.formatMessage({
      id: "models_elsewhere_unusable_in_models_folder_body",
      defaultMessage:
        "This is SurfSense’s own models folder, whose models are already listed.",
    }),
}

/** Why a found or picked file is not offered, in the interface's language. */
export function unusableReason(code: string, reason: string): string {
  return Object.hasOwn(unusableText, code)
    ? unusableText[code]()
    : (notRunnableLine(code) ?? reason)
}
