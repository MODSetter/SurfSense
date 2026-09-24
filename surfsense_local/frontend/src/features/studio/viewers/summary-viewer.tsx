import { Streamdown } from "streamdown"

import { intl } from "@/i18n/intl"

import type { ArtifactDetail } from "../api"
import { streamdownPlugins } from "./streamdown-config"
import { VIEWER_PADDING } from "./viewer-layout"

export function SummaryViewer({ artifact }: { artifact: ArtifactDetail }) {
  return (
    <div className={`${VIEWER_PADDING} text-sm leading-7`}>
      {/* mode="static": this content is already fully loaded, not
          streaming token-by-token like a chat reply. Streamdown renders
          complete content immediately either way — naming the mode just
          documents the intent instead of relying on the (also correct)
          default. */}
      <Streamdown
        mode="static"
        plugins={streamdownPlugins}
        linkSafety={{ enabled: true }}
      >
        {artifact.content ||
          intl.formatMessage({ id: "studio_summary_viewer_empty" })}
      </Streamdown>
    </div>
  )
}
