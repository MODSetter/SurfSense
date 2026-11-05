import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  CircleStopIcon,
  ExternalLinkIcon,
  PlayIcon,
  Trash2Icon,
} from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import { testConnectionSpeech } from "../models/api"
import { useServerVoices } from "./use-server-voices"
import { useVoiceTrial, type VoiceTrial } from "./use-voice-trial"

/** What a voice is heard saying: the interface's language, the one the user
 *  is likeliest to write podcasts in, since no server says what it speaks. */
const trialLine = () =>
  intl.formatMessage({
    id: "models_server_voices_trial_body",
    defaultMessage: "Hello. This is how your podcasts will sound.",
  })

function messageFrom(cause: unknown) {
  return cause instanceof Error
    ? cause.message
    : intl.formatMessage({
        id: "models_server_voices_request_error",
        defaultMessage: "The request failed",
      })
}

/** The voices a server audio model offers podcasts, under the model in use:
 *  the server's own list, or the user's, each heard before it is kept. */
export function ServerVoices() {
  const { voices, add, remove } = useServerVoices()
  const [draft, setDraft] = useState("")
  const [error, setError] = useState<string | null>(null)
  const read = voices.data
  const trials = useVoiceTrial(
    (voice) => `${read?.connection_id}/${read?.model}/${voice}`,
    (voice, signal) =>
      testConnectionSpeech(
        read!.connection_id,
        read!.model,
        voice,
        trialLine(),
        signal
      ),
    messageFrom
  )

  if (!voices.data) return null
  const { source, voices_page: page, problem } = voices.data
  const listed = source === "server"

  const submit = (event: React.SubmitEvent) => {
    event.preventDefault()
    const voice = draft.trim()
    if (!voice || add.isPending) return
    setError(null)
    add
      .mutateAsync({ voice, text: trialLine() })
      .then(() => setDraft(""))
      .catch((cause: unknown) => setError(messageFrom(cause)))
  }

  return (
    <section className="space-y-2">
      <h4 className="text-sm font-medium">
        {intl.formatMessage({
          id: "models_server_voices_title",
          defaultMessage: "Voices for this model",
        })}
      </h4>
      <p className="text-sm text-muted-foreground">
        {problem?.code === "no_usable_voices"
          ? intl.formatMessage({
              id: "models_server_voices_no_usable_body",
              defaultMessage:
                "This account has no voices its plan can use through the API. Upgrade your plan, or add a voice ID it can use.",
            })
          : problem
            ? intl.formatMessage(
                {
                  id: "models_server_voices_list_failed_body",
                  defaultMessage:
                    "Couldn’t read this server’s voices: {reason}",
                },
                { reason: problem.message }
              )
            : listed
              ? intl.formatMessage({
                  id: "models_server_voices_listed_body",
                  defaultMessage: "Listed by the server",
                })
              : source === "published"
                ? intl.formatMessage({
                    id: "models_server_voices_published_body",
                    defaultMessage:
                      "Published for this model. You can also add a voice by its ID; it’s played once before it’s kept.",
                  })
                : intl.formatMessage({
                    id: "models_server_voices_saved_body",
                    defaultMessage:
                      "This server doesn’t list its voices. Add the IDs you want; each is played once before it’s kept. A podcast needs one per speaker.",
                  })}
        {page ? (
          <>
            {" "}
            <a
              href={page}
              target="_blank"
              rel="noreferrer"
              // The desktop app refuses in-app navigation: the page opens in
              // the OS browser through the bridge. A bare browser follows href.
              onClick={(event) => {
                if (!window.surfsense?.openExternal) return
                event.preventDefault()
                void window.surfsense.openExternal(page)
              }}
              className="inline-flex items-center gap-1 text-foreground underline-offset-4 hover:underline"
            >
              {intl.formatMessage({
                id: "models_server_voices_page_link",
                defaultMessage: "See this model’s voices",
              })}
              <ExternalLinkIcon className="size-3.5" />
            </a>
          </>
        ) : null}
      </p>

      {voices.data.voices.length ? (
        <ScrollFade
          className="overflow-hidden rounded-lg border"
          viewportClassName="max-h-56"
        >
          <ul className="divide-y">
            {voices.data.voices.map(({ id: voice, label }) => (
              <VoiceRow
                key={voice}
                label={label}
                voice={voice}
                trial={trials.trial?.voice === voice ? trials.trial : null}
                error={
                  trials.failure?.voice === voice
                    ? trials.failure.message
                    : null
                }
                onPlay={() => void trials.play(voice)}
                onStop={trials.stop}
                onRemove={
                  voices.data.added.includes(voice)
                    ? () =>
                        void remove
                          .mutateAsync(voice)
                          .catch((cause: unknown) =>
                            setError(messageFrom(cause))
                          )
                    : undefined
                }
              />
            ))}
          </ul>
        </ScrollFade>
      ) : null}

      {listed ? null : (
        <form className="flex gap-2" onSubmit={submit}>
          <Input
            aria-label={intl.formatMessage({
              id: "models_server_voices_voice_aria",
              defaultMessage: "Voice ID",
            })}
            placeholder={intl.formatMessage({
              id: "models_server_voices_voice_placeholder",
              defaultMessage: "Voice ID",
            })}
            className="select-text"
            value={draft}
            maxLength={100}
            spellCheck={false}
            autoCapitalize="off"
            autoCorrect="off"
            onChange={(event) => setDraft(event.target.value)}
          />
          <Button type="submit" disabled={!draft.trim() || add.isPending}>
            {add.isPending ? <Spinner data-icon="inline-start" /> : null}
            {intl.formatMessage({
              id: "models_server_voices_add_button",
              defaultMessage: "Add and test",
            })}
          </Button>
        </form>
      )}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </section>
  )
}

function VoiceRow({
  voice,
  label,
  trial,
  error,
  onPlay,
  onStop,
  onRemove,
}: {
  voice: string
  /** Its name, or the id again where the server states none. */
  label: string
  trial: VoiceTrial | null
  error: string | null
  onPlay: () => void
  onStop: () => void
  onRemove?: () => void
}) {
  const playing = trial?.state === "playing"
  return (
    <li className="space-y-2 px-3 py-2">
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "flex-1 truncate text-sm select-text",
            label === voice && "font-mono"
          )}
        >
          {label}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          disabled={trial?.state === "loading"}
          aria-label={
            playing
              ? intl.formatMessage(
                  {
                    id: "models_server_voices_stop_aria",
                    defaultMessage: "Stop {voice}",
                  },
                  { voice: label }
                )
              : intl.formatMessage(
                  {
                    id: "models_server_voices_play_aria",
                    defaultMessage: "Play {voice}",
                  },
                  { voice: label }
                )
          }
          onClick={playing ? onStop : onPlay}
        >
          {trial?.state === "loading" ? (
            <Spinner />
          ) : playing ? (
            <CircleStopIcon />
          ) : (
            <PlayIcon />
          )}
        </Button>
        {onRemove ? (
          <Button
            type="button"
            variant="destructive"
            size="icon-xs"
            aria-label={intl.formatMessage(
              {
                id: "models_server_voices_remove_aria",
                defaultMessage: "Remove {voice}",
              },
              { voice: label }
            )}
            onClick={onRemove}
          >
            <Trash2Icon />
          </Button>
        ) : null}
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </li>
  )
}
