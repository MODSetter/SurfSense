import type { ReactNode } from "react"

import { ExternalLink } from "@/features/about/external-link"
import { useAppDetails } from "@/features/about/use-app-details"

import { guideUrl, type GuideSlug } from "./guide-links"

/** A "How to" link where a task starts: the guide for it, in the browser. */
export function GuideLink({
  guide,
  surface,
  children,
}: {
  guide: GuideSlug
  // utm_content, which says where in the app the guide was opened from.
  surface: string
  children: ReactNode
}) {
  const version = useAppDetails().data?.version
  return (
    <ExternalLink href={guideUrl(guide, surface, version)}>
      {children}
    </ExternalLink>
  )
}
