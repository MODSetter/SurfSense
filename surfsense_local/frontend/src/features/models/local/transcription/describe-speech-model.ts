import { intl } from "@/i18n/intl"

import type { LocalSpeechModel } from "./api"
import { languageName } from "./language-names"

const bytes = (value: number) =>
  value >= 1e9
    ? intl.formatNumber(value / 1e9, {
        style: "unit",
        unit: "gigabyte",
        maximumFractionDigits: 1,
      })
    : intl.formatNumber(value / 1e6, {
        style: "unit",
        unit: "megabyte",
        maximumFractionDigits: 0,
      })

/** What its download takes on disk. */
export function speechModelSize(model: LocalSpeechModel): string {
  return bytes(model.size_bytes)
}

/**
 * Build, download, language detection, and the one language when there is
 * only one; more are counted apart, where they expand.
 */
export function describeSpeechModel(model: LocalSpeechModel): string[] {
  return [
    model.quantization,
    speechModelSize(model),
    ...(model.detects_language
      ? [
          intl.formatMessage({
            id: "models_speech_model_detects_language_label",
            defaultMessage: "Detects the language",
          }),
        ]
      : []),
    ...(model.languages.length === 1 ? [languageName(model.languages[0])] : []),
  ]
}
