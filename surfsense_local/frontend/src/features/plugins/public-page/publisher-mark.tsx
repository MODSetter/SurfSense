import { Badge } from "@/components/ui/badge"
import { CheckmarkBadgeIcon } from "@/components/ui/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"

import type { RegistryEntry } from "../api"
import { isRegistryEntry, type ListedEntry } from "./listed-entry"

function verifiedLabel() {
  return intl.formatMessage({
    id: "plugins_registry_verified_label",
    defaultMessage: "Verified",
  })
}

function communityLabel() {
  return intl.formatMessage({
    id: "plugins_registry_community_label",
    defaultMessage: "Community",
  })
}

// What the mark means, in its tooltip.
function publisherNote(entry: RegistryEntry) {
  return entry.verified
    ? intl.formatMessage(
        {
          id: "plugins_registry_verified_tooltip",
          defaultMessage:
            "Verified publisher. SurfSense checked that {author} runs it.",
        },
        { author: entry.author }
      )
    : intl.formatMessage({
        id: "plugins_registry_community_tooltip",
        defaultMessage: "Community plugin. Not verified by SurfSense.",
      })
}

/**
 * Beside a third-party plugin's name: a checkmark when SurfSense's maintainers judged
 * that its author runs the server, else a Community badge. Raised above a Browse
 * card's stretched button (`z-10`), so hovering it shows its tooltip, not the card's.
 */
export function PublisherMark({ entry }: { entry: ListedEntry }) {
  if (!isRegistryEntry(entry)) return null
  return (
    <Tooltip>
      {/* The trigger wraps the mark, so a badge keeps its own slot and look. */}
      <TooltipTrigger
        render={<span className="relative z-10 inline-flex shrink-0" />}
      >
        {entry.verified ? (
          <span role="img" aria-label={verifiedLabel()} className="inline-flex">
            <CheckmarkBadgeIcon className="size-4 text-muted-foreground" />
          </span>
        ) : (
          // As the sidebar's "New" badge (components/feature-badge.tsx), a shade apart
          // from a Browse card's own muted fill and its hover.
          <Badge
            variant="secondary"
            className="h-4 rounded-md bg-accent px-1.5 text-[10px] text-accent-foreground"
          >
            {communityLabel()}
          </Badge>
        )}
      </TooltipTrigger>
      <TooltipContent>{publisherNote(entry)}</TooltipContent>
    </Tooltip>
  )
}
