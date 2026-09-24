import type { LocalAudioModel } from "./api"

const bytes = (value: number) =>
  value >= 1e9
    ? new Intl.NumberFormat(undefined, {
        style: "unit",
        unit: "gigabyte",
        maximumFractionDigits: 1,
      }).format(value / 1e9)
    : new Intl.NumberFormat(undefined, {
        style: "unit",
        unit: "megabyte",
        maximumFractionDigits: 0,
      }).format(value / 1e6)

function languages(codes: string[]): string {
  if (codes.length !== 1) return `${codes.length} languages`
  const names = new Intl.DisplayNames(undefined, { type: "language" })
  return names.of(codes[0]) ?? codes[0]
}

/** Build, download, memory while voicing, voices, languages; the row dots them. */
export function describeAudioModel(model: LocalAudioModel): string[] {
  return [
    model.quantization,
    bytes(model.size_bytes),
    `${bytes(model.peak_mb * 1e6)} while voicing`,
    `${model.voice_count} voices`,
    languages(model.languages),
  ]
}
