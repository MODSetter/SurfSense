import { languageName } from "@/features/models/local/transcription/language-names"
import { useSpeechLanguageRead } from "@/features/models/local/transcription/language/use-speech-language"
import { intl } from "@/i18n/intl"

/**
 * Says a transcript may read less well when the model detected a language it
 * is not listed for. Silent while no speech model is chosen to compare with.
 */
export function UnlistedLanguageLine({ language }: { language: string }) {
  const intent = useSpeechLanguageRead()
  const listed = intent.data?.languages
  const base = language.split("-")[0]
  if (!listed || listed.includes(language) || listed.includes(base)) {
    return null
  }
  return (
    <p>
      {intl.formatMessage(
        {
          id: "sources_row_unlisted_language_body",
          defaultMessage:
            "{language} (detected) · the transcript may be less accurate",
        },
        { language: languageName(language) }
      )}
    </p>
  )
}
