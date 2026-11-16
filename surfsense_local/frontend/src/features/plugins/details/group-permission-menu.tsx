import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDownIcon, EllipsisIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import { PERMISSION_ICON, groupStateLabel } from "./permission-copy"
import { PERMISSIONS, type ToolPermission } from "./tool-permission"

const CUSTOM = "custom"

/** The state a group's tools share; picking one sets every tool that can take it. Custom only reports tools that differ. */
export function GroupPermissionMenu({
  group,
  current,
  canTake,
  onPick,
}: {
  group: string
  current: ToolPermission | null
  /** False when no tool in the group can take the choice, so it is closed. */
  canTake: (permission: ToolPermission) => boolean
  onPick: (permission: ToolPermission) => void
}) {
  const CurrentIcon = current ? PERMISSION_ICON[current] : EllipsisIcon
  const customLabel = intl.formatMessage({
    id: "plugins_group_custom_label",
    defaultMessage: "Custom",
  })
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            type="button"
            size="sm"
            variant="secondary"
            aria-label={intl.formatMessage(
              {
                id: "plugins_group_permission_aria",
                defaultMessage: "Permission for every {group} tool",
              },
              { group }
            )}
          >
            <CurrentIcon data-icon="inline-start" />
            {current ? groupStateLabel(current) : customLabel}
            <ChevronDownIcon data-icon="inline-end" />
          </Button>
        }
      />
      <DropdownMenuContent align="end" sideOffset={4} className="w-48">
        <DropdownMenuRadioGroup
          value={current ?? CUSTOM}
          onValueChange={(value: string) => {
            if (value !== CUSTOM) onPick(value as ToolPermission)
          }}
        >
          {PERMISSIONS.map((permission) => {
            const Icon = PERMISSION_ICON[permission]
            return (
              <DropdownMenuRadioItem
                key={permission}
                value={permission}
                disabled={!canTake(permission)}
                closeOnClick
              >
                <Icon />
                {groupStateLabel(permission)}
              </DropdownMenuRadioItem>
            )
          })}
          <DropdownMenuRadioItem value={CUSTOM} closeOnClick>
            <EllipsisIcon />
            {customLabel}
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
