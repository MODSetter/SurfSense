import { intl } from "@/i18n/intl"

import { PodcastBriefForm } from "../podcast-brief-form"
import { usePodcastBrief } from "../use-podcast-brief"
import type { FormatOptions } from "./format-options"

/** A podcast is generated from its reviewed brief, so it waits for the brief. A
 *  server model with no voices yet can voice nothing: set them up first. */
export function usePodcastOptions(
  format: string,
  workspaceId: number,
  onSetUpVoices: () => void
): FormatOptions | null {
  const podcast = usePodcastBrief(format === "podcast" ? workspaceId : null)
  if (format !== "podcast") return null

  const needsVoices =
    podcast.opened?.voices_source === "saved" &&
    podcast.opened.voices.length === 0
  const panel =
    podcast.brief && podcast.opened ? (
      <PodcastBriefForm
        brief={podcast.brief}
        voices={podcast.opened.voices}
        languages={podcast.opened.languages}
        voicesSource={podcast.opened.voices_source}
        voicesProblem={podcast.opened.problem}
        voicedBy={podcast.opened.voiced_by}
        onSetUpVoices={onSetUpVoices}
        onChange={podcast.setBrief}
      />
    ) : (
      <p className="text-sm text-muted-foreground">
        {podcast.error ??
          intl.formatMessage({
            id: "studio_composer_brief_status",
            defaultMessage: "Preparing the brief…",
          })}
      </p>
    )
  return {
    panel,
    job: { format, options: podcast.brief ?? undefined },
    ready: podcast.brief != null && !needsVoices,
  }
}
