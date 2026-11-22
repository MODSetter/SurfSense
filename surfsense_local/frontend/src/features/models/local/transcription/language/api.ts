import { ApiError, requestJson } from "@/lib/api"

const URL = "/llm/selection/speech_to_text/language"

/** The language intent of the speech model in use: `auto` or a listed code. */
export type SpeechLanguage = {
  language: string
  /** ISO 639-1 codes of the languages the model is listed for. */
  languages: string[]
  detects_language: boolean
}

/** Null while no speech model is chosen, which has no intent to read. */
export async function readSpeechLanguage(
  signal?: AbortSignal
): Promise<SpeechLanguage | null> {
  try {
    return await requestJson<SpeechLanguage>(URL, { signal })
  } catch (error) {
    if (error instanceof ApiError && error.code === "needs_speech_model") {
      return null
    }
    throw error
  }
}

export function writeSpeechLanguage(language: string): Promise<SpeechLanguage> {
  return requestJson<SpeechLanguage>(URL, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
  })
}
