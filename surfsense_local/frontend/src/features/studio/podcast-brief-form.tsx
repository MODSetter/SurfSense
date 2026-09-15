import { useId, type ComponentProps } from "react"

import { Button } from "@/components/ui/button"
import { PlusIcon, Trash2Icon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

import {
  MAX_SPEAKERS,
  PODCAST_DURATIONS,
  PODCAST_ROLES,
  PODCAST_STYLES,
  type PodcastBrief,
  type PodcastSpeaker,
  type Voice,
} from "./api"

const DURATION_HINTS = { short: "~3 min", standard: "~8 min", long: "~15 min" }
// Roles by slot when a speaker is added without a say from the user.
const ROLE_BY_SLOT = ["host", "guest", "expert", "cohost", "narrator"] as const

const languageNames = new Intl.DisplayNames(["en"], { type: "language" })
const title = (word: string) => word[0].toUpperCase() + word.slice(1)

export function PodcastBriefForm({
  brief,
  voices,
  onChange,
}: {
  brief: PodcastBrief
  voices: Voice[]
  onChange: (brief: PodcastBrief) => void
}) {
  const id = useId()
  const languages = [...new Set(voices.map((voice) => voice.language))]
  const spoken = voices.filter((voice) => voice.language === brief.language)
  const taken = new Set(brief.speakers.map((speaker) => speaker.voice))
  const free = spoken.find((voice) => !taken.has(voice.id))

  const update = (patch: Partial<PodcastBrief>) =>
    onChange({ ...brief, ...patch })

  // Every speaker moves to the new language: voices are per language.
  const changeLanguage = (language: string) => {
    const next = voices.filter((voice) => voice.language === language)
    update({
      language,
      speakers: brief.speakers
        .slice(0, next.length)
        .map((speaker, index) => ({ ...speaker, voice: next[index].id })),
    })
  }

  const updateSpeaker = (index: number, patch: Partial<PodcastSpeaker>) =>
    update({
      speakers: brief.speakers.map((speaker, at) =>
        at === index ? { ...speaker, ...patch } : speaker
      ),
    })

  const addSpeaker = () => {
    if (!free) return
    const slot = brief.speakers.length
    const role = ROLE_BY_SLOT[slot] ?? "guest"
    update({
      speakers: [
        ...brief.speakers,
        {
          name: title(role === "cohost" ? "co-host" : role),
          role,
          voice: free.id,
        },
      ],
    })
  }

  const removeSpeaker = (index: number) =>
    update({ speakers: brief.speakers.filter((_, at) => at !== index) })

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <Field label="Language" htmlFor={`${id}-language`}>
          <Select
            id={`${id}-language`}
            value={brief.language}
            onChange={(event) => changeLanguage(event.target.value)}
          >
            {languages.map((language) => (
              <option key={language} value={language}>
                {languageNames.of(language) ?? language}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Style" htmlFor={`${id}-style`}>
          <Select
            id={`${id}-style`}
            value={brief.style}
            onChange={(event) =>
              update({ style: event.target.value as PodcastBrief["style"] })
            }
          >
            {PODCAST_STYLES.map((style) => (
              <option key={style} value={style}>
                {title(style)}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="space-y-1">
        <p className="text-xs font-medium text-muted-foreground">Length</p>
        <div className="grid grid-cols-3 gap-1.5">
          {PODCAST_DURATIONS.map((duration) => (
            <Button
              key={duration}
              type="button"
              variant="outline"
              size="sm"
              aria-pressed={brief.duration === duration}
              className={cn(
                brief.duration === duration && "border-primary bg-primary/5"
              )}
              onClick={() => update({ duration })}
            >
              {title(duration)}
              <span className="text-muted-foreground">
                {DURATION_HINTS[duration]}
              </span>
            </Button>
          ))}
        </div>
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground">Speakers</p>
          <Button
            type="button"
            variant="ghost"
            size="xs"
            disabled={!free || brief.speakers.length >= MAX_SPEAKERS}
            onClick={addSpeaker}
          >
            <PlusIcon data-icon="inline-start" />
            Add speaker
          </Button>
        </div>
        {brief.speakers.map((speaker, index) => (
          <fieldset
            key={index}
            aria-label={`Speaker ${index + 1}`}
            className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-1.5"
          >
            <Input
              aria-label="Name"
              className="select-text"
              value={speaker.name}
              maxLength={40}
              onChange={(event) =>
                updateSpeaker(index, { name: event.target.value })
              }
            />
            <Select
              aria-label="Role"
              value={speaker.role}
              onChange={(event) =>
                updateSpeaker(index, {
                  role: event.target.value as PodcastSpeaker["role"],
                })
              }
            >
              {PODCAST_ROLES.map((role) => (
                <option key={role} value={role}>
                  {role === "cohost" ? "Co-host" : title(role)}
                </option>
              ))}
            </Select>
            <Select
              aria-label="Voice"
              value={speaker.voice}
              onChange={(event) =>
                updateSpeaker(index, { voice: event.target.value })
              }
            >
              {spoken.map((voice) => (
                <option
                  key={voice.id}
                  value={voice.id}
                  disabled={taken.has(voice.id) && voice.id !== speaker.voice}
                >
                  {voice.label}
                </option>
              ))}
            </Select>
            {brief.speakers.length > 1 ? (
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                aria-label={`Remove speaker ${index + 1}`}
                onClick={() => removeSpeaker(index)}
              >
                <Trash2Icon />
              </Button>
            ) : (
              <span className="size-6" />
            )}
          </fieldset>
        ))}
      </div>
    </div>
  )
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string
  htmlFor: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <label
        htmlFor={htmlFor}
        className="text-xs font-medium text-muted-foreground"
      >
        {label}
      </label>
      {children}
    </div>
  )
}

function Select({ className, ...props }: ComponentProps<"select">) {
  return (
    <select
      className={cn(
        "h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring/70 disabled:opacity-50 dark:bg-input/30",
        className
      )}
      {...props}
    />
  )
}
