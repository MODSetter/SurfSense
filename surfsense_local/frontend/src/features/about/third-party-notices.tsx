import { Button } from "@/components/ui/button"
import { errorToast } from "@/features/feedback/error-toast"
import { intl } from "@/i18n/intl"

import { aboutBridge } from "./use-app-details"

// The notices the installer ships for everything it bundles, opened as the file itself.
export function ThirdPartyNotices() {
  const about = aboutBridge()
  if (about?.openNotices === undefined) return null
  const openNotices = about.openNotices

  const open = async () => {
    const reason = await openNotices()
    if (reason) {
      errorToast(
        intl.formatMessage({
          id: "about_notices_open_error",
          defaultMessage: "Couldn’t open the third-party notices",
        }),
        { description: reason }
      )
    }
  }

  return (
    <Button
      type="button"
      variant="link"
      className="h-auto w-fit p-0 text-muted-foreground hover:text-foreground"
      onClick={() => void open()}
    >
      {intl.formatMessage({
        id: "about_notices_open_button",
        defaultMessage: "Third-party notices",
      })}
    </Button>
  )
}
