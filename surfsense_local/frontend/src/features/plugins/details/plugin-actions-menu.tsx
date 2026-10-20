import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  EllipsisIcon,
  ExternalLinkIcon,
  LicenseIcon,
  PencilIcon,
  RefreshCwIcon,
  ShuffleIcon,
  Trash2Icon,
} from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { Plugin } from "../api"
import { EditConnectionDialog } from "../connection/edit-connection-button"
import { PluginOwnAppDialog } from "../sign-in/own-app/plugin-own-app-dialog"
import { EditHeadersDialog } from "./edit-headers-button"
import { openRegistrySubmission } from "./registry-submission"

const LICENSE_FAILURES = new Set<Plugin["check_failure"]>([
  "needs_license",
  "license_expired",
  "license_revoked",
  "license_invalid",
])

type Editing = "connection" | "headers" | "own_app"

/** A plugin's less frequent actions, beside its one main action; a disconnected plugin can only
 * be removed. On and off is the composer's "+ › Plugins". */
export function PluginActionsMenu({
  plugin,
  held,
  checking,
  onCheck,
  onRemove,
  onOpenLicense,
}: {
  plugin: Plugin
  /** Held by the third-party switch: only removing, which reaches no server, is offered. */
  held: boolean
  checking: boolean
  onCheck: () => void
  onRemove: () => void
  onOpenLicense?: () => void
}) {
  const [editing, setEditing] = useState<Editing | null>(null)
  // Connected, so a change goes in place; a plugin not connected connects from its main action.
  const working =
    !held && !plugin.disconnected && plugin.check_failure !== "sign_in"
  // A key that still works can change, and an open server can take an optional one.
  const editsConnection =
    working &&
    plugin.source === "custom" &&
    (plugin.auth_type === "headers" || plugin.auth_type === "none")
  const editsHeaders =
    working && plugin.source !== "custom" && plugin.auth_type === "headers"
  const changesOwnApp =
    !held && plugin.own_app && !plugin.disconnected && !plugin.check_failure
  const editingOpen = (open: boolean) => {
    if (!open) setEditing(null)
  }
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              aria-label={intl.formatMessage(
                {
                  id: "plugins_actions_trigger_aria",
                  defaultMessage: "More actions for {plugin}",
                },
                { plugin: plugin.name }
              )}
            >
              <EllipsisIcon />
            </Button>
          }
        />
        <DropdownMenuContent align="end" sideOffset={8} className="w-52">
          {plugin.disconnected || held ? null : (
            <>
              <DropdownMenuGroup>
                <DropdownMenuItem disabled={checking} onClick={onCheck}>
                  <RefreshCwIcon />
                  {intl.formatMessage({
                    id: "plugins_actions_check_label",
                    defaultMessage: "Refresh tools",
                  })}
                </DropdownMenuItem>
                {editsConnection ? (
                  <DropdownMenuItem onClick={() => setEditing("connection")}>
                    <PencilIcon />
                    {intl.formatMessage({
                      id: "plugins_actions_edit_connection_label",
                      defaultMessage: "Edit connection",
                    })}
                  </DropdownMenuItem>
                ) : null}
                {editsHeaders ? (
                  <DropdownMenuItem onClick={() => setEditing("headers")}>
                    <PencilIcon />
                    {intl.formatMessage({
                      id: "plugins_actions_edit_headers_label",
                      defaultMessage: "Edit headers",
                    })}
                  </DropdownMenuItem>
                ) : null}
                {changesOwnApp ? (
                  <DropdownMenuItem onClick={() => setEditing("own_app")}>
                    <ShuffleIcon />
                    {intl.formatMessage({
                      id: "plugins_actions_change_own_app_label",
                      defaultMessage: "Change OAuth app",
                    })}
                  </DropdownMenuItem>
                ) : null}
                {LICENSE_FAILURES.has(plugin.check_failure) && onOpenLicense ? (
                  <DropdownMenuItem onClick={onOpenLicense}>
                    <LicenseIcon />
                    {intl.formatMessage({
                      id: "plugins_actions_license_label",
                      defaultMessage: "License settings",
                    })}
                  </DropdownMenuItem>
                ) : null}
                {plugin.source === "custom" ? (
                  <DropdownMenuItem
                    onClick={() => openRegistrySubmission(plugin)}
                  >
                    <ExternalLinkIcon />
                    {intl.formatMessage({
                      id: "plugins_actions_submit_label",
                      defaultMessage: "Submit to the registry",
                    })}
                  </DropdownMenuItem>
                ) : null}
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
            </>
          )}
          <DropdownMenuGroup>
            <DropdownMenuItem variant="destructive" onClick={onRemove}>
              <Trash2Icon />
              {intl.formatMessage({
                id: "plugins_actions_remove_label",
                defaultMessage: "Remove",
              })}
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      {editsConnection ? (
        <EditConnectionDialog
          plugin={plugin}
          open={editing === "connection"}
          onOpenChange={editingOpen}
        />
      ) : null}
      {editsHeaders ? (
        <EditHeadersDialog
          plugin={plugin}
          open={editing === "headers"}
          onOpenChange={editingOpen}
        />
      ) : null}
      {changesOwnApp ? (
        <PluginOwnAppDialog
          plugin={plugin}
          reason="chosen"
          open={editing === "own_app"}
          onOpenChange={editingOpen}
        />
      ) : null}
    </>
  )
}
