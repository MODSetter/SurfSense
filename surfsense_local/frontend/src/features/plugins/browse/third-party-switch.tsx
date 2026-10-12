import { useState } from "react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Switch } from "@/components/ui/switch"
import { intl } from "@/i18n/intl"

/**
 * Plugins SurfSense does not publish stay unused until this is on. Turning it
 * on says what that means first; turning it off needs no warning.
 */
export function ThirdPartySwitch({
  allowed,
  onChange,
}: {
  allowed: boolean
  onChange: (allowed: boolean) => void
}) {
  const [asking, setAsking] = useState(false)
  const label = intl.formatMessage({
    id: "plugins_third_party_label",
    defaultMessage: "Allow third-party plugins",
  })
  return (
    <>
      <Switch
        checked={allowed}
        aria-label={label}
        onCheckedChange={(checked) =>
          checked ? setAsking(true) : onChange(false)
        }
      />
      <AlertDialog open={asking} onOpenChange={setAsking}>
        <AlertDialogContent className="select-none">
          <AlertDialogHeader>
            <AlertDialogTitle>
              {intl.formatMessage({
                id: "plugins_third_party_dialog_title",
                defaultMessage: "Allow third-party plugins?",
              })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {intl.formatMessage({
                id: "plugins_third_party_dialog_body",
                defaultMessage:
                  "Other people run these servers. What the agent sends a tool goes to its publisher, and SurfSense doesn’t review changes to their servers. You still choose each tool, and tools that can make changes ask first.",
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>
              {intl.formatMessage({
                id: "plugins_third_party_dialog_cancel_button",
                defaultMessage: "Cancel",
              })}
            </AlertDialogCancel>
            <AlertDialogAction onClick={() => onChange(true)}>
              {intl.formatMessage({
                id: "plugins_third_party_dialog_confirm_button",
                defaultMessage: "Allow",
              })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
