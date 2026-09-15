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

// The formats offered before the API answers, and if it never does. The
// backend's catalog replaces this as soon as it loads.
export const STUDIO_CATALOG: StudioFormat[] = [
  {
    key: "summary",
    label: "Summary",
    requires_roles: ["generation"],
    available: true,
    unavailable_reason: null,
  },
  {
    key: "docx",
    label: "Document",
    requires_roles: ["generation"],
    available: true,
    unavailable_reason: null,
  },
  {
    key: "pptx",
    label: "Slides",
    requires_roles: ["generation"],
    available: true,
    unavailable_reason: null,
  },
  {
    key: "xlsx",
    label: "Spreadsheet",
    requires_roles: ["generation"],
    available: true,
    unavailable_reason: null,
  },
  {
    key: "html",
    label: "Web page",
    requires_roles: ["generation"],
    available: true,
    unavailable_reason: null,
  },
  {
    key: "pdf",
    label: "PDF",
    requires_roles: ["generation"],
    available: true,
    unavailable_reason: null,
  },
  {
    key: "mindmap",
    label: "Mind map",
    requires_roles: ["generation"],
    available: true,
    unavailable_reason: null,
  },
  {
    key: "flashcards",
    label: "Flashcards",
    requires_roles: ["generation"],
    available: true,
    unavailable_reason: null,
  },
  {
    key: "quiz",
    label: "Quiz",
    requires_roles: ["generation"],
    available: true,
    unavailable_reason: null,
  },
  {
    key: "podcast",
    label: "Podcast",
    requires_roles: ["generation"],
    available: true,
    unavailable_reason: null,
  },
  {
    key: "image",
    label: "Image",
    requires_roles: ["image_generation", "generation"],
    available: true,
    unavailable_reason: null,
  },
  {
    key: "infographic",
    label: "Infographic",
    requires_roles: ["image_generation", "generation"],
    available: true,
    unavailable_reason: null,
  },
]
