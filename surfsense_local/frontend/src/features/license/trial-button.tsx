import type { MouseEvent } from "react"

import { buttonVariants } from "@/components/ui/button"
import { ExternalLinkIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import { TRIAL_URL } from "./license-links"

// The main way in for someone without a license; it stays a link because it
// leaves the app for the OS browser.
export function TrialButton() {
  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (!window.surfsense?.openExternal) return
    event.preventDefault()
    void window.surfsense.openExternal(TRIAL_URL)
  }
  return (
    <a
      href={TRIAL_URL}
      target="_blank"
      rel="noreferrer"
      onClick={onClick}
      className={buttonVariants()}
    >
      {intl.formatMessage({
        id: "license_settings_trial_link",
        defaultMessage: "Start a free trial",
      })}
      <ExternalLinkIcon aria-hidden="true" />
    </a>
  )
}
