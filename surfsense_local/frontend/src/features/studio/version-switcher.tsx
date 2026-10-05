import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDownIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { Artifact } from "./api"
import type { VersionedArtifact } from "./artifact-versions"

function versionLabel(number: number) {
  return intl.formatMessage(
    {
      id: "studio_version_switcher_item_label",
      defaultMessage: "v{version, number}",
    },
    { version: number }
  )
}

/** Why a version cannot be opened yet, or null when it can. */
function unopenedStatus(version: Artifact) {
  switch (version.status) {
    case "ready":
      return null
    case "pending":
    case "processing":
      return intl.formatMessage({
        id: "studio_version_switcher_running_status",
        defaultMessage: "In progress",
      })
    case "cancelled":
      return intl.formatMessage({
        id: "studio_version_switcher_cancelled_status",
        defaultMessage: "Cancelled",
      })
    case "failed":
      return intl.formatMessage({
        id: "studio_version_switcher_failed_status",
        defaultMessage: "Failed",
      })
  }
}

/** Picks which of a document's versions the viewer shows. */
export function VersionSwitcher({
  versions,
  openId,
  onOpen,
}: {
  /** Oldest first. */
  versions: VersionedArtifact[]
  openId: number
  onOpen: (artifactId: number) => void
}) {
  const open = versions.find((version) => version.id === openId)
  if (!open) return null

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="gap-1 px-2 text-muted-foreground tabular-nums data-popup-open:bg-accent"
            aria-label={intl.formatMessage(
              {
                id: "studio_version_switcher_aria",
                defaultMessage: "Showing v{version, number}. Choose a version",
              },
              { version: open.version.number }
            )}
          >
            {versionLabel(open.version.number)}
            <ChevronDownIcon data-icon="inline-end" />
          </Button>
        }
      />
      <DropdownMenuContent align="end" sideOffset={8} className="min-w-36">
        <DropdownMenuGroup>
          <DropdownMenuLabel>
            {intl.formatMessage({
              id: "studio_version_switcher_title",
              defaultMessage: "Versions",
            })}
          </DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={String(openId)}
            onValueChange={(value) => onOpen(Number(value))}
          >
            {versions.map((version) => {
              const status = unopenedStatus(version)
              return (
                <DropdownMenuRadioItem
                  key={version.id}
                  value={String(version.id)}
                  // Base UI radio items stay open on pick; a pick here is done.
                  closeOnClick
                  disabled={status !== null}
                  className="tabular-nums"
                >
                  {versionLabel(version.version.number)}
                  {status ? (
                    <>
                      {" "}
                      <span className="text-xs text-muted-foreground">
                        {status}
                      </span>
                    </>
                  ) : null}
                </DropdownMenuRadioItem>
              )
            })}
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
