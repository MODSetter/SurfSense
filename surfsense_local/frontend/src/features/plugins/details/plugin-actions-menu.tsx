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
  KeyIcon,
  RefreshCwIcon,
  Trash2Icon,
} from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { Plugin } from "../api"
import { openRegistrySubmission } from "./registry-submission"

/** A plugin's less frequent actions; a disconnected plugin can only be removed. On and off is the composer's "+ › Plugins". A custom one can be offered to the registry, and one signing in by itself can sign in with the user's own app, for an organization allowing only its approved one. */
export function PluginActionsMenu({
  plugin,
  checking,
  onCheck,
  onRemove,
  onOwnApp,
}: {
  plugin: Plugin
  checking: boolean
  onCheck: () => void
  onRemove: () => void
  onOwnApp: () => void
}) {
  return (
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
        {plugin.disconnected ? null : (
          <>
            <DropdownMenuGroup>
              <DropdownMenuItem disabled={checking} onClick={onCheck}>
                <RefreshCwIcon />
                {intl.formatMessage({
                  id: "plugins_actions_check_label",
                  defaultMessage: "Refresh tools",
                })}
              </DropdownMenuItem>
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
              {plugin.auth_type === "oauth" && !plugin.own_app ? (
                <DropdownMenuItem onClick={onOwnApp}>
                  <KeyIcon />
                  {intl.formatMessage({
                    id: "plugins_actions_own_app_label",
                    defaultMessage: "Use your own OAuth app",
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
  )
}
