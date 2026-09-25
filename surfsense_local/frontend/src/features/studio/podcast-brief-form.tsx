import { useId } from "react"

import { Button } from "@/components/ui/button"
import { PlusIcon, Trash2Icon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { intl } from "@/i18n/intl"

import {
  MAX_SPEAKERS,
  PODCAST_DURATIONS,
  PODCAST_ROLES,
  PODCAST_STYLES,
  type PodcastBrief,
  type PodcastSpeaker,
  type Voice,
} from "./api"

type PodcastStyle = PodcastBrief["style"]
type PodcastDuration = PodcastBrief["duration"]
type PodcastRole = PodcastSpeaker["role"]

const STYLE_LABELS: Record<PodcastStyle, () => string> = {
  conversational: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_style_conversational_label",
      defaultMessage: "Conversational",
    }),
  interview: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_style_interview_label",
      defaultMessage: "Interview",
    }),
  debate: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_style_debate_label",
      defaultMessage: "Debate",
    }),
  monologue: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_style_monologue_label",
      defaultMessage: "Monologue",
    }),
  narrative: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_style_narrative_label",
      defaultMessage: "Narrative",
    }),
}
const DURATION_LABELS: Record<PodcastDuration, () => string> = {
  short: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_length_short_label",
      defaultMessage: "Short",
    }),
  standard: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_length_standard_label",
      defaultMessage: "Standard",
    }),
  long: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_length_long_label",
      defaultMessage: "Long",
    }),
}
const DURATION_HINTS: Record<PodcastDuration, () => string> = {
  short: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_length_short_body",
      defaultMessage: "~3 min",
    }),
  standard: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_length_standard_body",
      defaultMessage: "~8 min",
    }),
  long: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_length_long_body",
      defaultMessage: "~15 min",
    }),
}
const ROLE_LABELS: Record<PodcastRole, () => string> = {
  host: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_role_host_label",
      defaultMessage: "Host",
    }),
  cohost: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_role_cohost_label",
      defaultMessage: "Co-host",
    }),
  guest: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_role_guest_label",
      defaultMessage: "Guest",
    }),
  expert: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_role_expert_label",
      defaultMessage: "Expert",
    }),
  narrator: () =>
    intl.formatMessage({
      id: "studio_podcast_brief_role_narrator_label",
      defaultMessage: "Narrator",
    }),
}
// Roles by slot when a speaker is added without a say from the user.
const ROLE_BY_SLOT = ["host", "guest", "expert", "cohost", "narrator"] as const

// A new speaker's default name is script content sent to the backend, so it
// stays English whatever the interface language.
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
  const languages = [...new Set(voices.flatMap((voice) => voice.languages))]
  const spoken = voices.filter((voice) =>
    voice.languages.includes(brief.language)
  )
  const taken = new Set(brief.speakers.map((speaker) => speaker.voice))
  const free = spoken.find((voice) => !taken.has(voice.id))

  const update = (patch: Partial<PodcastBrief>) =>
    onChange({ ...brief, ...patch })

  // A speaker keeps a voice that speaks the new language, as a Supertonic
  // voice speaks all of them; the rest take that language's free voices.
  const changeLanguage = (language: string) => {
    const next = voices.filter((voice) => voice.languages.includes(language))
    const kept = new Set(
      brief.speakers
        .map((speaker) => speaker.voice)
        .filter((voice) => next.some((candidate) => candidate.id === voice))
    )
    const free = next.filter((voice) => !kept.has(voice.id))
    update({
      language,
      speakers: brief.speakers
        .slice(0, next.length)
        .map((speaker) =>
          kept.has(speaker.voice)
            ? speaker
            : { ...speaker, voice: free.shift()?.id ?? speaker.voice }
        ),
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
        <Field
          label={intl.formatMessage({
            id: "studio_podcast_brief_language_label",
            defaultMessage: "Language",
          })}
          htmlFor={`${id}-language`}
        >
          <Select
            id={`${id}-language`}
            value={brief.language}
            onChange={(event) => changeLanguage(event.target.value)}
          >
            {languages.map((language) => (
              <option key={language} value={language}>
                {intl.formatDisplayName(language, { type: "language" }) ??
                  language}
              </option>
            ))}
          </Select>
        </Field>
        <Field
          label={intl.formatMessage({
            id: "studio_podcast_brief_style_label",
            defaultMessage: "Style",
          })}
          htmlFor={`${id}-style`}
        >
          <Select
            id={`${id}-style`}
            value={brief.style}
            onChange={(event) =>
              update({ style: event.target.value as PodcastBrief["style"] })
            }
          >
            {PODCAST_STYLES.map((style) => (
              <option key={style} value={style}>
                {STYLE_LABELS[style]()}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="space-y-1">
        <p className="text-xs font-medium text-muted-foreground">
          {intl.formatMessage({
            id: "studio_podcast_brief_length_label",
            defaultMessage: "Length",
          })}
        </p>
        <div className="grid grid-cols-3 gap-1.5">
          {PODCAST_DURATIONS.map((duration) => (
            <Button
              key={duration}
              type="button"
              variant="outline"
              size="sm"
              aria-pressed={brief.duration === duration}
              // The outline variant sets dark: border and background; override both.
              className="aria-pressed:border-primary aria-pressed:bg-primary/5 dark:aria-pressed:border-primary dark:aria-pressed:bg-primary/5"
              onClick={() => update({ duration })}
            >
              {DURATION_LABELS[duration]()}
              <span className="text-muted-foreground">
                {DURATION_HINTS[duration]()}
              </span>
            </Button>
          ))}
        </div>
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground">
            {intl.formatMessage({
              id: "studio_podcast_brief_speakers_label",
              defaultMessage: "Speakers",
            })}
          </p>
          <Button
            type="button"
            variant="ghost"
            size="xs"
            disabled={!free || brief.speakers.length >= MAX_SPEAKERS}
            onClick={addSpeaker}
          >
            <PlusIcon data-icon="inline-start" />
            {intl.formatMessage({
              id: "studio_podcast_brief_add_speaker_button",
              defaultMessage: "Add speaker",
            })}
          </Button>
        </div>
        {brief.speakers.map((speaker, index) => (
          <fieldset
            key={index}
            aria-label={intl.formatMessage(
              {
                id: "studio_podcast_brief_speaker_aria",
                defaultMessage: "Speaker {number, number}",
              },
              {
                number: index + 1,
              }
            )}
            className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-1.5"
          >
            <Input
              aria-label={intl.formatMessage({
                id: "studio_podcast_brief_speaker_name_aria",
                defaultMessage: "Name",
              })}
              className="select-text"
              value={speaker.name}
              maxLength={40}
              onChange={(event) =>
                updateSpeaker(index, { name: event.target.value })
              }
            />
            <Select
              aria-label={intl.formatMessage({
                id: "studio_podcast_brief_speaker_role_aria",
                defaultMessage: "Role",
              })}
              value={speaker.role}
              onChange={(event) =>
                updateSpeaker(index, {
                  role: event.target.value as PodcastSpeaker["role"],
                })
              }
            >
              {PODCAST_ROLES.map((role) => (
                <option key={role} value={role}>
                  {ROLE_LABELS[role]()}
                </option>
              ))}
            </Select>
            <Select
              aria-label={intl.formatMessage({
                id: "studio_podcast_brief_speaker_voice_aria",
                defaultMessage: "Voice",
              })}
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
                variant="destructive"
                size="icon-xs"
                aria-label={intl.formatMessage(
                  {
                    id: "studio_podcast_brief_remove_speaker_aria",
                    defaultMessage: "Remove speaker {number, number}",
                  },
                  {
                    number: index + 1,
                  }
                )}
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
