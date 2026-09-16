import type { ComponentType } from "react"

import type { ArtifactDetail } from "../api"
import { DocumentViewer } from "./document-viewer"
import { MindmapViewer } from "./mindmap-viewer"
import { StudyViewer } from "./study-viewer"

export interface ArtifactViewerProps {
  artifact: ArtifactDetail
}

// Frontend-only concern, same idea as FORMAT_ICONS in studio-formats.ts: the
// backend's format catalog has no notion of a viewer, so this is the single
// place format keys map to one. A format without an entry here falls back to
// DocumentViewer, so a new backend format renders (as raw content) instead of
// breaking the panel — add an entry here once it needs a dedicated view.
const ARTIFACT_VIEWERS: Record<string, ComponentType<ArtifactViewerProps>> = {
  mindmap: ({ artifact }) => (
    <MindmapViewer markdown={artifact.content ?? ""} />
  ),
  flashcards: ({ artifact }) => (
    <StudyViewer artifactId={artifact.id} format="flashcards" />
  ),
  quiz: ({ artifact }) => (
    <StudyViewer artifactId={artifact.id} format="quiz" />
  ),
}

export function getArtifactViewer(
  format: string
): ComponentType<ArtifactViewerProps> {
  return ARTIFACT_VIEWERS[format] ?? DocumentViewer
}
