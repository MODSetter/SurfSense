import { useState } from "react"

import { Button } from "@/components/ui/button"

import type { Plugin } from "../../api"
import type { OwnAppReason } from "./own-app-reason"
import { PluginOwnAppDialog } from "./plugin-own-app-dialog"

/** Connects a plugin whose provider takes only apps registered with it, through the user's own. */
export function OwnAppButton({
  plugin,
  reason,
  label,
  size = "xs",
  className,
}: {
  plugin: Plugin
  reason: OwnAppReason
  label: string
  size?: "xs" | "sm"
  className?: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button
        type="button"
        size={size}
        variant="secondary"
        className={className}
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
