import { useQuery } from "@tanstack/react-query"

import {
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from "@/components/ui/dropdown-menu"
import {
  EllipsisIcon,
  GridViewIcon,
  PlugIcon,
  PlusIcon,
  Settings2Icon,
} from "@/components/ui/icons"
import { Switch } from "@/components/ui/switch"
import {
  HINTED_ROW_CLASS,
  HintedLabel,
  MenuItemHint,
} from "@/features/chat/menu-item-hint"
import { intl } from "@/i18n/intl"

import {
  listPlugins,
  pluginsQueryKey,
  thirdPartyAllowed,
  thirdPartyQueryKey,
  type Plugin,
} from "../api"
import { usePluginChanges } from "../details/use-plugin-changes"
import { PluginIcon } from "../plugin-icon"
import type { PluginsStart } from "../plugins-settings"

function PluginSwitchItem({
  plugin,
  usable,
  onEnabled,
}: {
  plugin: Plugin
  // False for a third-party plugin while third-party plugins are off.
  usable: boolean
  onEnabled: (enabled: boolean) => void
}) {
  const on = plugin.enabled && usable
  const hint = usable
    ? null
    : intl.formatMessage({
        id: "plugins_menu_third_party_off_tooltip",
        defaultMessage: "Third-party plugins are off",
      })
  const row = (
    // Stays open on click, so the switch is seen to move.
    <DropdownMenuItem
      role="menuitemcheckbox"
      aria-checked={on}
      closeOnClick={false}
      disabled={!usable}
      className={HINTED_ROW_CLASS}
      onClick={() => onEnabled(!plugin.enabled)}
    >
      <PluginIcon
        id={plugin.id}
        name={plugin.name}
        hasIcon={plugin.source !== "custom"}
        firstParty={plugin.source === "first_party"}
        className="size-5 text-xs"
      />
      {hint ? (
        <HintedLabel label={plugin.name} hint={hint} />
      ) : (
        <span className="min-w-0 flex-1 truncate">{plugin.name}</span>
      )}
      {/* Drawn only: the row is the control, and a second one would nest. */}
      <Switch
        size="sm"
        checked={on}
        tabIndex={-1}
        aria-hidden
        className="pointer-events-none"
      />
    </DropdownMenuItem>
  )
  return hint ? <MenuItemHint hint={hint}>{row}</MenuItemHint> : row
}

/**
 * The composer's "+ › Plugins": ways to add and manage plugins in Settings, then
 * a switch per connected plugin, which turns it on or off for every Agentic chat.
 */
export function PluginsMenu({
  onOpen,
}: {
  // Opens Settings › Plugins, on Browse or Add custom plugin when given.
  onOpen: (start?: PluginsStart) => void
}) {
  const changes = usePluginChanges()
  const plugins = useQuery({
    queryKey: pluginsQueryKey,
    queryFn: ({ signal }) => listPlugins(signal),
  })
  const thirdParty = useQuery({
    queryKey: thirdPartyQueryKey,
    queryFn: ({ signal }) => thirdPartyAllowed(signal),
  })
  // A disconnected plugin has no switch to give: it comes back through Connect.
  const connected = (plugins.data ?? []).filter(
    (plugin) => !plugin.disconnected
  )
  const thirdPartyOn = thirdParty.data ?? false

  return (
    <DropdownMenuSub>
      <DropdownMenuSubTrigger>
        <PlugIcon />
        {intl.formatMessage({
          id: "plugins_menu_trigger_label",
          defaultMessage: "Plugins",
        })}
      </DropdownMenuSubTrigger>
      <DropdownMenuSubContent className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              <PlusIcon />
              {intl.formatMessage({
                id: "plugins_menu_add_label",
                defaultMessage: "Add plugin",
              })}
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuGroup>
                <DropdownMenuItem onClick={() => onOpen("browse")}>
                  <GridViewIcon />
                  {intl.formatMessage({
                    id: "plugins_menu_browse_label",
                    defaultMessage: "Browse plugins",
                  })}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => onOpen("add")}>
                  <EllipsisIcon />
                  {intl.formatMessage({
                    id: "plugins_menu_add_custom_label",
                    defaultMessage: "Add custom plugin",
                  })}
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
          <DropdownMenuItem onClick={() => onOpen()}>
            <Settings2Icon />
            {intl.formatMessage({
              id: "plugins_menu_manage_label",
              defaultMessage: "Manage plugins",
            })}
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuLabel>
            {intl.formatMessage({
              id: "plugins_menu_scope_label",
              defaultMessage: "Applies to all Agentic chats",
            })}
          </DropdownMenuLabel>
          {connected.length === 0 ? (
            <DropdownMenuItem disabled>
              {intl.formatMessage({
                id: "plugins_menu_none_empty",
                defaultMessage: "No plugins connected",
              })}
            </DropdownMenuItem>
          ) : (
            connected.map((plugin) => (
              <PluginSwitchItem
                key={plugin.id}
                plugin={plugin}
                usable={plugin.source === "first_party" || thirdPartyOn}
                onEnabled={(enabled) =>
                  changes.plugin.mutate({ plugin: plugin.id, enabled })
                }
              />
            ))
          )}
        </DropdownMenuGroup>
      </DropdownMenuSubContent>
    </DropdownMenuSub>
  )
}
