import { Streamdown } from "streamdown"

import { intl } from "@/i18n/intl"

import { fileUrl, type ArtifactDetail } from "../api"
import { streamdownPlugins } from "./streamdown-config"
import { VIEWER_PADDING } from "./viewer-layout"

export function PodcastViewer({ artifact }: { artifact: ArtifactDetail }) {
  const primary = artifact.files.find((file) => file.role === "primary")
  const src = primary ? fileUrl(artifact.id, primary.role) : null

  return (
    <div className={`space-y-4 ${VIEWER_PADDING}`}>
      {src ? (
        // biome-ignore lint/a11y/useMediaCaption: The transcript is rendered directly below the player.
        <audio className="mb-15 w-full" controls src={src} />
      ) : null}
      {artifact.content ? (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">
            {intl.formatMessage({
              id: "studio_podcast_viewer_transcript_title",
            })}
          </p>
          <Streamdown
            className="text-sm leading-7"
            mode="static"
            plugins={streamdownPlugins}
            linkSafety={{ enabled: true }}
          >
            {artifact.content}
          </Streamdown>
        </div>
      ) : null}
    </div>
  )
}
