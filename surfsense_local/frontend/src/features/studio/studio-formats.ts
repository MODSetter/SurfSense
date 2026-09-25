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

import { intl } from "@/i18n/intl"

import type { StudioFormat } from "./api"

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

// The backend's catalog sends English labels; a known key shows its own.
const FORMAT_LABELS: Record<string, () => string> = {
  summary: () =>
    intl.formatMessage({
      id: "studio_format_summary_label",
      defaultMessage: "Summary",
    }),
  docx: () =>
    intl.formatMessage({
      id: "studio_format_docx_label",
      defaultMessage: "Word",
    }),
  pptx: () =>
    intl.formatMessage({
      id: "studio_format_pptx_label",
      defaultMessage: "Slides",
    }),
  xlsx: () =>
    intl.formatMessage({
      id: "studio_format_xlsx_label",
      defaultMessage: "Spreadsheet",
    }),
  html: () =>
    intl.formatMessage({
      id: "studio_format_html_label",
      defaultMessage: "Web page",
    }),
  pdf: () =>
    intl.formatMessage({
      id: "studio_format_pdf_label",
      defaultMessage: "PDF",
    }),
  mindmap: () =>
    intl.formatMessage({
      id: "studio_format_mindmap_label",
      defaultMessage: "Mind map",
    }),
  flashcards: () =>
    intl.formatMessage({
      id: "studio_format_flashcards_label",
      defaultMessage: "Flashcards",
    }),
  quiz: () =>
    intl.formatMessage({
      id: "studio_format_quiz_label",
      defaultMessage: "Quiz",
    }),
  podcast: () =>
    intl.formatMessage({
      id: "studio_format_podcast_label",
      defaultMessage: "Podcast",
    }),
  image: () =>
    intl.formatMessage({
      id: "studio_format_image_label",
      defaultMessage: "Image",
    }),
  infographic: () =>
    intl.formatMessage({
      id: "studio_format_infographic_label",
      defaultMessage: "Infographic",
    }),
}

export function formatLabel(entry: { key: string; label: string }): string {
  return FORMAT_LABELS[entry.key]?.() ?? entry.label
}

// The formats offered before the API answers, and if it never does. The
// backend's catalog replaces this as soon as it loads.
export function studioCatalog(): StudioFormat[] {
  return Object.keys(FORMAT_LABELS).map((key) => ({
    key,
    label: FORMAT_LABELS[key](),
    requires_model_types:
      key === "image" || key === "infographic"
        ? ["image_gen", "text_gen"]
        : ["text_gen"],
    available: true,
    unavailable_reason: null,
  }))
}
