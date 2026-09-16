import type { ComponentType } from "react"

import type { ArtifactDetail } from "../api"
import { DocumentViewer } from "./document-viewer"
import { MediaViewer } from "./media-viewer"
import { MindmapViewer } from "./mindmap-viewer"
import { StudyViewer } from "./study-viewer"

export interface ArtifactViewerProps {
  artifact: ArtifactDetail
}

// The layout contract every viewer is registered under, enforced by the one
// wrapper in ArtifactPanel rather than each viewer guessing its own height:
//   - "fill": the viewer is a stage that must occupy the full height it's
//     given (a canvas, a centered card) and manages its own overflow.
//   - "flow": the viewer has no opinion on height — it renders at its
//     natural size and the shared stage scrolls around it.
export type ViewerMode = "fill" | "flow"

interface ViewerEntry {
  component: ComponentType<ArtifactViewerProps>
  mode: ViewerMode
}

// Frontend-only concern, same idea as FORMAT_ICONS in studio-formats.ts: the
// backend's format catalog has no notion of a viewer, so this is the single
// place format keys map to one. A format without an entry here falls back to
// DocumentViewer, so a new backend format renders (as raw content) instead of
// breaking the panel — add an entry here once it needs a dedicated view.
const ARTIFACT_VIEWERS: Record<string, ViewerEntry> = {
  mindmap: {
    component: ({ artifact }) => (
      <MindmapViewer markdown={artifact.content ?? ""} />
    ),
    mode: "fill",
  },
  flashcards: {
    component: ({ artifact }) => (
      <StudyViewer artifactId={artifact.id} format="flashcards" />
    ),
    mode: "fill",
  },
  quiz: {
    component: ({ artifact }) => (
      <StudyViewer artifactId={artifact.id} format="quiz" />
    ),
    mode: "fill",
  },
  image: { component: MediaViewer, mode: "flow" },
  infographic: { component: MediaViewer, mode: "flow" },
}

const DEFAULT_ENTRY: ViewerEntry = { component: DocumentViewer, mode: "flow" }

export function getArtifactViewer(format: string): ViewerEntry {
  return ARTIFACT_VIEWERS[format] ?? DEFAULT_ENTRY
}
