import type { MouseEvent } from "react"

import { buttonVariants } from "@/components/ui/button"
import { ExternalLinkIcon } from "@/components/ui/icons"
import { useAppDetails } from "@/features/about/use-app-details"
import { intl } from "@/i18n/intl"

import { trialUrl, type TrialSurface } from "./license-links"

// The main way in for someone without a license; it stays a link because it
// leaves the app for the OS browser.
export function TrialButton({
  surface = "license_trial",
  label,
  variant = "default",
  size = "default",
}: {
  /** Where in the app it is, which also picks the page it opens. */
  surface?: TrialSurface
  /** The caller's own words; Settings › License's "Start a free trial" by default. */
  label?: string
  variant?: "default" | "outline"
  size?: "default" | "sm"
}) {
  const href = trialUrl(useAppDetails().data?.version, surface)
  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (!window.surfsense?.openExternal) return
    event.preventDefault()
    void window.surfsense.openExternal(href)
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      onClick={onClick}
      data-slot="button"
      className={buttonVariants({ variant, size })}
    >
      {label ??
        intl.formatMessage({
          id: "license_settings_trial_link",
          defaultMessage: "Start a free trial",
        })}
      <ExternalLinkIcon aria-hidden="true" />
    </a>
  )
}
