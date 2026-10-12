import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { PlusIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

export function NoPluginsConnected({
  onBrowse,
  onAdd,
}: {
  onBrowse: () => void
  onAdd: () => void
}) {
  return (
    <Empty className="border py-10">
      <EmptyHeader>
        <EmptyTitle>
          {intl.formatMessage({
            id: "plugins_empty_title",
            defaultMessage: "No plugins connected",
          })}
        </EmptyTitle>
        <EmptyDescription>
          {intl.formatMessage({
            id: "plugins_empty_body",
            defaultMessage:
              "Give the agent tools: browse plugins, or add your own server.",
          })}
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent className="flex-row justify-center">
        <Button type="button" size="sm" onClick={onBrowse}>
          {intl.formatMessage({
            id: "plugins_empty_browse_button",
            defaultMessage: "Browse plugins",
          })}
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onAdd}>
          <PlusIcon data-icon="inline-start" />
          {intl.formatMessage({
            id: "plugins_empty_add_button",
            defaultMessage: "Add custom plugin",
          })}
        </Button>
      </EmptyContent>
    </Empty>
  )
}
