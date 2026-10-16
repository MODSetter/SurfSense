import { useId } from "react"

import { Select } from "@/components/ui/select"
import { intl } from "@/i18n/intl"

import { namedLanguages } from "../language-names"
import { useSpeechLanguage } from "./use-speech-language"

const AUTO = "auto"

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "models_speech_language_request_error",
        defaultMessage: "The request failed",
      })
}

/**
 * The language recordings and voice input are in. Detection is offered only
 * by a model that has it; the interface's language is never assumed.
 */
export function SpeechLanguageSelect() {
  const titleId = useId()
  const bodyId = useId()
  const { language, choose } = useSpeechLanguage()
  const intent = language.data
  if (!intent) return null

  return (
    <section className="flex flex-col gap-2 rounded-lg border px-3 py-2.5">
      <div className="flex items-center justify-between gap-8">
        <div className="flex flex-col gap-1">
          <h3 id={titleId} className="text-sm font-medium">
            {intl.formatMessage({
              id: "models_speech_language_title",
              defaultMessage: "Spoken language",
            })}
          </h3>
          <p id={bodyId} className="text-sm text-pretty text-muted-foreground">
            {intl.formatMessage({
              id: "models_speech_language_body",
              defaultMessage:
                "The language your recordings and voice input are in.",
            })}
          </p>
        </div>
        <Select
          aria-labelledby={titleId}
          aria-describedby={bodyId}
          className="w-48"
          // The choice shows while it saves, not the one it replaces.
          value={choose.isPending ? choose.variables : intent.language}
          disabled={choose.isPending}
          onChange={(event) => choose.mutate(event.target.value)}
        >
          {intent.detects_language ? (
            <option value={AUTO}>
              {intl.formatMessage({
                id: "models_speech_language_auto_label",
                defaultMessage: "Detect automatically",
              })}
            </option>
          ) : null}
          {namedLanguages(intent.languages).map(({ code, name }) => (
            <option key={code} value={code}>
              {name}
            </option>
          ))}
        </Select>
      </div>
      {choose.isError ? (
        <p className="text-sm text-destructive">{messageFrom(choose.error)}</p>
      ) : null}
    </section>
  )
}
