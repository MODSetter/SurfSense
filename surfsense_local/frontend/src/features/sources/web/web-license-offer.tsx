import { Button } from "@/components/ui/button"
import { GlobalSearchIcon } from "@/components/ui/icons"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { TrialButton } from "@/features/license/trial-button"
import { intl } from "@/i18n/intl"

/** In place of the search: an offer, never a wall. `reason` is the plugin host's word. */
export function WebLicenseOffer({
  reason,
  onOpenLicense,
}: {
  reason: string
  onOpenLicense: () => void
}) {
  return (
    <Empty className="border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <GlobalSearchIcon />
        </EmptyMedia>
        <EmptyTitle>
          {intl.formatMessage({
            id: "sources_web_license_title",
            defaultMessage:
              "Adding from the web comes with a SurfSense license",
          })}
        </EmptyTitle>
        <EmptyDescription>{offerText(reason)}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent className="flex-row justify-center gap-2">
        {reason === "missing_license" ? <TrialButton /> : null}
        <Button type="button" variant="outline" onClick={onOpenLicense}>
          {intl.formatMessage({
            id: "sources_web_license_settings_button",
            defaultMessage: "License settings",
          })}
        </Button>
      </EmptyContent>
    </Empty>
  )
}

function offerText(reason: string): string {
  if (reason === "missing_license") {
    return intl.formatMessage({
      id: "sources_web_license_missing_body",
      defaultMessage:
        "Search the web or paste links, and add what you find as sources.",
    })
  }
  if (reason === "expired") {
    return intl.formatMessage({
      id: "sources_web_license_expired_body",
      defaultMessage:
        "Your SurfSense license has expired. Renew it to keep adding sources from the web.",
    })
  }
  return intl.formatMessage({
    id: "sources_web_license_refused_body",
    defaultMessage:
      "Your SurfSense license wasn’t accepted. Check it in License settings.",
  })
}
