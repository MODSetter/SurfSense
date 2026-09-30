import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { ExternalLinkIcon, PlayIcon, Trash2Icon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { testConnectionSpeech } from "../models/api"
import type { ServerVoicesRead } from "./api"
import { useServerVoices } from "./use-server-voices"

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

  if (!voices.data) return null
  const { source, voices_page: page } = voices.data
  const listed = source === "server"

  const submit = (event: React.FormEvent) => {
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
        {listed
          ? intl.formatMessage({
              id: "models_server_voices_listed_body",
              defaultMessage: "Listed by the server",
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
        <ul className="divide-y rounded-lg border">
          {voices.data.voices.map((voice) => (
            <VoiceRow
              key={voice}
              voice={voice}
              read={voices.data}
              onRemove={
                listed
                  ? undefined
                  : () =>
                      void remove
                        .mutateAsync(voice)
                        .catch((cause: unknown) => setError(messageFrom(cause)))
              }
            />
          ))}
        </ul>
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
  read,
  onRemove,
}: {
  voice: string
  read: ServerVoicesRead
  onRemove?: () => void
}) {
  const [clip, setClip] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(
    () => () => {
      if (clip) URL.revokeObjectURL(clip)
    },
    [clip]
  )

  const play = () => {
    setPlaying(true)
    setError(null)
    testConnectionSpeech(read.connection_id, read.model, voice, trialLine())
      .then((blob) => setClip(URL.createObjectURL(blob)))
      .catch((cause: unknown) => setError(messageFrom(cause)))
      .finally(() => setPlaying(false))
  }

  return (
    <li className="space-y-2 px-3 py-2">
      <div className="flex items-center gap-2">
        <span className="flex-1 truncate font-mono text-sm select-text">
          {voice}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          disabled={playing}
          aria-label={intl.formatMessage(
            {
              id: "models_server_voices_play_aria",
              defaultMessage: "Play {voice}",
            },
            { voice }
          )}
          onClick={play}
        >
          {playing ? <Spinner /> : <PlayIcon />}
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
              { voice }
            )}
            onClick={onRemove}
          >
            <Trash2Icon />
          </Button>
        ) : null}
      </div>
      {clip ? (
        <audio
          controls
          autoPlay
          src={clip}
          className="w-full"
          aria-label={intl.formatMessage(
            {
              id: "models_server_voices_clip_aria",
              defaultMessage: "{voice}, as the server voices it",
            },
            { voice }
          )}
        />
      ) : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </li>
  )
}
