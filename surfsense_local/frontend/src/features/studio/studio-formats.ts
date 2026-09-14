import type { ComponentType } from "react"

import {
  AiSearchLinesIcon,
  Cards01Icon,
  ChartHistogramIcon,
  File02Icon,
  Image01Icon,
  NetworkIcon,
  Pdf01Icon,
  PodcastIcon,
  Presentation02Icon,
  Quiz02Icon,
  WebDesign01Icon,
  Xls01Icon,
} from "@/components/ui/icons"

// Frontend-only concern: the backend's format catalog has no notion of an
// icon, so this is the single place format keys map to one.
export const FORMAT_ICONS: Record<
  string,
  ComponentType<{ className?: string }>
> = {
  summary: AiSearchLinesIcon,
  docx: File02Icon,
  pptx: Presentation02Icon,
  xlsx: Xls01Icon,
  html: WebDesign01Icon,
  pdf: Pdf01Icon,
  mindmap: NetworkIcon,
  flashcards: Cards01Icon,
  quiz: Quiz02Icon,
  podcast: PodcastIcon,
  image: Image01Icon,
  infographic: ChartHistogramIcon,
}
