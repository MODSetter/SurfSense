import { intl } from "@/i18n/intl"
import type { AppDetails } from "@/lib/api"

import { CopySystemInfoButton } from "./copy-system-info-button"
import { systemInfo } from "./system-info"

export function Troubleshooting({ details }: { details: AppDetails }) {
  return (
    <div className="mt-8 flex items-start justify-between gap-8">
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-medium">
          {intl.formatMessage({
            id: "about_troubleshooting_title",
            defaultMessage: "Troubleshooting",
          })}
        </h3>
        <p className="text-sm text-pretty text-muted-foreground">
          {intl.formatMessage({
            id: "about_troubleshooting_body",
            defaultMessage:
              "Copy details about this app and your computer to include in a bug report.",
          })}
        </p>
      </div>
      <CopySystemInfoButton text={systemInfo(details)} />
    </div>
  )
}
