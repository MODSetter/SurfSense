import { useState } from "react"

import { Button } from "@/components/ui/button"

import type { Plugin } from "../../api"
import type { OwnAppReason } from "./own-app-reason"
import { PluginOwnAppDialog } from "./plugin-own-app-dialog"

/** Opens the user's own OAuth app for a saved plugin: to set one up where its provider takes
 * no other, to use one where an organization blocks the sign-in, or to change it. */
export function OwnAppButton({
  plugin,
  reason,
  label,
  primary = false,
}: {
  plugin: Plugin
  reason: OwnAppReason
  label: string
  /** The plugin's one way to connect, shown as its main action. */
  primary?: boolean
}) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button
        type="button"
        size="xs"
        variant={primary ? "secondary" : "ghost"}
        onClick={() => setOpen(true)}
      >
        {label}
      </Button>
      <PluginOwnAppDialog
        plugin={plugin}
        reason={reason}
        open={open}
        onOpenChange={setOpen}
      />
    </>
  )
}
