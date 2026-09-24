import { intl } from "@/i18n/intl"

import type { LocalAudioModel } from "./api"

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

function languages(codes: string[]): string {
  if (codes.length !== 1)
    return intl.formatMessage(
      {
        id: "models_audio_model_languages_label",
        defaultMessage: "{count, plural, one {# language} other {# languages}}",
      },
      { count: codes.length }
    )
  return intl.formatDisplayName(codes[0], { type: "language" }) ?? codes[0]
}

/** Build, download, memory while voicing, voices, languages; the row dots them. */
export function describeAudioModel(model: LocalAudioModel): string[] {
  return [
    model.quantization,
    bytes(model.size_bytes),
    intl.formatMessage(
      {
        id: "models_audio_model_peak_memory_label",
        defaultMessage: "{size} while voicing",
      },
      {
        size: bytes(model.peak_mb * 1e6),
      }
    ),
    intl.formatMessage(
      {
        id: "models_audio_model_voices_label",
        defaultMessage: "{count, plural, one {# voice} other {# voices}}",
      },
      { count: model.voice_count }
    ),
    languages(model.languages),
  ]
}
