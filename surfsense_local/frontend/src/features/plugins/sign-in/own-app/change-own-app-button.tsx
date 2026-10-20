import { useState } from "react"

import { Button } from "@/components/ui/button"
import { intl } from "@/i18n/intl"

import type { Plugin } from "../../api"
import { PluginOwnAppDialog } from "./plugin-own-app-dialog"

/** Only on a plugin signed in with the user's own app: a new secret, or another app. */
export function ChangeOwnAppButton({ plugin }: { plugin: Plugin }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button
        type="button"
        size="xs"
        variant="ghost"
        onClick={() => setOpen(true)}
      >
        {intl.formatMessage({
          id: "plugins_own_app_change_button",
          defaultMessage: "Change OAuth app",
        })}
      </Button>
      <PluginOwnAppDialog
        plugin={plugin}
        reason="chosen"
        open={open}
        onOpenChange={setOpen}
      />
    </>
  )
}
