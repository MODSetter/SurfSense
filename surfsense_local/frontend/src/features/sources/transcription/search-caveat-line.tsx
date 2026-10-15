import { useEmbeddingIndex } from "@/features/embedding/use-embedding-index"
import { languageName } from "@/features/models/local/transcription/language-names"
import { intl } from "@/i18n/intl"

// No endpoint says which languages an embedder reads. The bundled bge-small
// is the English-only one the app ships; any other is not assumed to be.
const ENGLISH_ONLY_EMBEDDERS = new Set(["bge-small-en-v1.5"])

/**
 * Says search finds a transcript best with questions in its own language,
 * while the library's index reads English only. Nothing is switched for it.
 */
export function SearchCaveatLine({
  language,
}: {
  // Null when the model could not name the recording's language.
  language: string | null
}) {
  const index = useEmbeddingIndex()
  const embedder = index.data?.active?.spec.id
  if (!embedder || !ENGLISH_ONLY_EMBEDDERS.has(embedder)) return null
  return (
    <p>
      {language
        ? intl.formatMessage(
            {
              id: "sources_row_search_caveat_body",
              defaultMessage:
                "This recording is in {language}. Search finds it best with questions in {language}; add it to a chat to have all of it read.",
            },
            { language: languageName(language) }
          )
        : intl.formatMessage({
            id: "sources_row_search_caveat_unidentified_body",
            defaultMessage:
              "This recording’s language wasn’t identified. Search finds it best with questions in its language; add it to a chat to have all of it read.",
          })}
    </p>
  )
}
