/** The 26 languages Nemotron's card measures at 30% error or better. */
export const NEMOTRON_LANGUAGES = [
  "it",
  "es",
  "en",
  "pt",
  "hi",
  "ko",
  "de",
  "fr",
  "ru",
  "ja",
  "nl",
  "vi",
  "uk",
  "tr",
  "ar",
  "pl",
  "zh",
  "nb",
  "fi",
  "bg",
  "cs",
  "sk",
  "sv",
  "hr",
  "ro",
  "da",
]

/** Stands in for audio.cpp's catalog row for a recogniser, as the API sends it. */
export function fakeSpeechRow(
  overrides: Record<string, unknown> = {},
  build: Record<string, unknown> = {}
) {
  return {
    id: "nemotron-3.5-asr-streaming-0.6b",
    source: "local",
    origin: "curated",
    name: "Nemotron 3.5 ASR",
    family: "Nemotron",
    types: ["speech_to_text"],
    known: true,
    approximate: false,
    selectable_for: ["speech_to_text"],
    support: {
      context: null,
      reads_images: false,
      tools: null,
      reasoning: null,
    },
    runnable: true,
    not_runnable_reason: null,
    default_quantization: "Q8_0",
    recommended: false,
    engine: "audiocpp",
    lead: { quantization: "Q8_0", why: "default" },
    voicing: null,
    transcription: {
      peak_mb: 1776,
      window_s: 28,
      detects_language: true,
      languages: NEMOTRON_LANGUAGES,
    },
    builds: [
      {
        catalog_id: "opaque-nemotron",
        quantization: "Q8_0",
        footprint_bytes: 930_600_000,
        files: [],
        fit: null,
        badge: null,
        can_install: true,
        installed_as: null,
        selected: false,
        recommended: false,
        reads_images: false,
        projector_checked: false,
        bundled: false,
        ...build,
      },
    ],
    ...overrides,
  }
}

/** What the build reads once on disk, and once chosen for speech recognition. */
export const SPEECH_INSTALLED = {
  installed_as: "nemotron-3.5-asr-streaming-0.6b-q8_0",
}
export const SPEECH_IN_USE = {
  ...SPEECH_INSTALLED,
  selected: true,
  selected_for: ["speech_to_text"],
}
