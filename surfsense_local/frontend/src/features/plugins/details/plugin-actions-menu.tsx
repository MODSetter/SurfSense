import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { EllipsisIcon, RefreshCwIcon, Trash2Icon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { Plugin } from "../api"

/** A plugin's less frequent actions; a disconnected plugin can only be removed. On and off is the composer's "+ › Plugins". */
export function PluginActionsMenu({
  plugin,
  checking,
  onCheck,
  onRemove,
}: {
  plugin: Plugin
  checking: boolean
  onCheck: () => void
  onRemove: () => void
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
      <DropdownMenuContent align="end" sideOffset={8} className="w-40">
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
