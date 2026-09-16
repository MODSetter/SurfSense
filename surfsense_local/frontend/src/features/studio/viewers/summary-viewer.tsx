import { code } from "@streamdown/code"
import { createMathPlugin } from "@streamdown/math"
import { Streamdown } from "streamdown"

import type { ArtifactDetail } from "../api"

// Same code/math plugins chat uses (src/features/chat/message.tsx), for a
// consistent look. `mode="static"` is explicit: this content is already
// fully loaded, not streaming token-by-token like a chat reply — Streamdown
// renders complete content immediately either way, but naming the mode
// documents the intent instead of relying on the (also correct) default.
const plugins = {
  code,
  math: createMathPlugin({ singleDollarTextMath: true }),
}

export function SummaryViewer({ artifact }: { artifact: ArtifactDetail }) {
  return (
    <div className="px-5 py-4 text-sm leading-7">
      <Streamdown mode="static" plugins={plugins} linkSafety={{ enabled: true }}>
        {artifact.content || "This artifact has no text body."}
      </Streamdown>
    </div>
  )
}
