import type { ComponentType } from "react"

import type { ArtifactDetail } from "../api"
import { DocumentViewer } from "./document-viewer"
import { DocxViewer } from "./docx-viewer"
import { FlashcardsViewer } from "./flashcards/flashcards-viewer"
import { HtmlViewer } from "./html-viewer"
import { MediaViewer } from "./media-viewer"
import { MindmapViewer } from "./mindmap-viewer"
import { PdfViewer } from "./pdf-viewer"
import { PodcastViewer } from "./podcast-viewer"
import { PptxViewer } from "./pptx-viewer"
import { QuizViewer } from "./quiz/quiz-viewer"
import { SummaryViewer } from "./summary-viewer"
import { XlsxViewer } from "./xlsx-viewer"

export interface ArtifactViewerProps {
  artifact: ArtifactDetail
  // The header's actions slot (left of Download), shared across every
  // format. A viewer with its own controls (mindmap's fit button, pdf's
  // zoom buttons) portals them in there instead of drawing its own toolbar;
  // null until ArtifactPanel's ref mounts, so most viewers just ignore it.
  actionsContainer: HTMLElement | null
}

// Frontend-only concern, same idea as FORMAT_ICONS in studio-formats.ts: the
// backend's format catalog has no notion of a viewer, so this is the single
// place format keys map to one. A format without an entry here falls back to
// DocumentViewer, so a new backend format renders (as raw content) instead of
// breaking the panel — add an entry here once it needs a dedicated view.
//
// Every viewer renders into the same full-height stage (see ArtifactPanel);
// flowing content (text, an image) simply doesn't fill it, which is fine —
// the stage scrolls around whatever the viewer renders.
const ARTIFACT_VIEWERS: Record<string, ComponentType<ArtifactViewerProps>> = {
  mindmap: ({ artifact, actionsContainer }) => (
    <MindmapViewer
      markdown={artifact.content ?? ""}
      actionsContainer={actionsContainer}
    />
  ),
  // Keyed by id+generation so switching decks — or a regenerate bumping
  // generation — remounts with a clean run instead of carrying over stale
  // in-memory progress from the useState seeded at mount.
  flashcards: ({ artifact, actionsContainer }) => (
    <FlashcardsViewer
      key={`${artifact.id}:${artifact.generation}`}
      artifact={artifact}
      actionsContainer={actionsContainer}
    />
  ),
  quiz: ({ artifact }) => (
    <QuizViewer key={`${artifact.id}:${artifact.generation}`} artifact={artifact} />
  ),
  image: MediaViewer,
  infographic: MediaViewer,
  xlsx: XlsxViewer,
  pdf: PdfViewer,
  pptx: PptxViewer,
  html: HtmlViewer,
  docx: DocxViewer,
  summary: SummaryViewer,
  podcast: PodcastViewer,
}

export function getArtifactViewer(
  format: string
): ComponentType<ArtifactViewerProps> {
  return ARTIFACT_VIEWERS[format] ?? DocumentViewer
}
