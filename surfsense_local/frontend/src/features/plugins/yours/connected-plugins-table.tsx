import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ChevronRightIcon } from "@/components/ui/icons"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { Plugin } from "../api"
import { ConnectPluginButton } from "../details/connect-plugin-button"
import { PluginIcon } from "../plugin-icon"
import { notConnected } from "../not-connected"
import { connectReason } from "./connect-reason"
import { pluginStatus } from "./plugin-status"
import { TONE_CLASS } from "./status-tone"
import { pluginTypeLabel } from "./plugin-type-label"

/** One row per connected plugin; the name is a button that opens its details, stretched over the row. */

// A table row cannot be rounded, so its cells carry the hover and the first and last round it.
const CELL =
  "py-1.5 transition-colors group-hover/row:bg-muted/50 first:rounded-l-lg last:rounded-r-lg"
export function ConnectedPluginsTable({
  plugins,
  thirdPartyAllowed,
  onOpen,
}: {
  plugins: Plugin[]
  thirdPartyAllowed: boolean
  onOpen: (id: string) => void
}) {
  // As in the chats dialog: the line between two rows shows only while neither is hovered.
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const line = (above: Plugin | undefined, below: Plugin | undefined) =>
    above?.id !== hoveredId && below?.id !== hoveredId
      ? "border-border/60"
      : "border-transparent"
  const leave = (id: string) =>
    setHoveredId((current) => (current === id ? null : current))

  // Widths come from the header, so a long status or a sign-in under way never moves the columns.
  return (
    <Table className="table-fixed">
      <TableHeader>
        <TableRow
          className={cn("hover:bg-transparent", line(undefined, plugins[0]))}
        >
          <TableHead className="w-2/5 text-muted-foreground">
            {intl.formatMessage({
              id: "plugins_list_plugin_label",
              defaultMessage: "Plugin",
            })}
          </TableHead>
          <TableHead className="w-1/5 text-muted-foreground">
            {intl.formatMessage({
              id: "plugins_list_type_label",
              defaultMessage: "Type",
            })}
          </TableHead>
          <TableHead className="text-muted-foreground">
            {intl.formatMessage({
              id: "plugins_list_status_label",
              defaultMessage: "Status",
            })}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {plugins.map((plugin, index) => {
          const status = pluginStatus(plugin, thirdPartyAllowed)
          return (
            <TableRow
              key={plugin.id}
              className={cn(
                "group/row relative hover:bg-transparent",
                // The row's own bottom line; TableBody drops the last row's.
                line(plugin, plugins[index + 1])
              )}
              onMouseEnter={() => setHoveredId(plugin.id)}
              onMouseLeave={() => leave(plugin.id)}
            >
              <TableCell className={CELL}>
                <Button
                  type="button"
                  variant="bare"
                  static
                  className="flex max-w-full min-w-0 items-center gap-3 text-left font-medium after:absolute after:inset-0 after:rounded-lg focus-visible:ring-0 focus-visible:after:ring-2 focus-visible:after:ring-ring"
                  onClick={() => onOpen(plugin.id)}
                >
                  <PluginIcon
                    id={plugin.id}
                    name={plugin.name}
                    hasIcon={plugin.source !== "custom"}
                    firstParty={plugin.source === "first_party"}
                    className="size-7 text-xs"
                  />
                  <span className="truncate">{plugin.name}</span>
                </Button>
              </TableCell>
              <TableCell className={cn(CELL, "truncate text-muted-foreground")}>
                {pluginTypeLabel(plugin.source)}
              </TableCell>
              <TableCell className={cn(CELL, TONE_CLASS[status.tone])}>
                <span className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-2">
                    {notConnected(plugin, thirdPartyAllowed) ? (
                      <>
                        {/* Positioned, so it sits above the row's stretched link. */}
                        <span className="relative flex shrink-0 items-center">
                          <ConnectPluginButton
                            plugin={plugin}
                            size="sm"
                            // As tall as the plugin's icon, so the row keeps its height; the row's text size.
                            className="text-sm"
                          />
                        </span>
                        {/* The space keeps a screen reader from saying "ConnectKey refused". */}{" "}
                        <span className="truncate text-muted-foreground">
                          {connectReason(plugin)}
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="truncate">{status.label}</span>
                        {/* The space keeps a screen reader from saying "OnNew tools". */}
                        {status.badge && (
                          <>
                            {" "}
                            <Badge variant="secondary">{status.badge}</Badge>
                          </>
                        )}
                      </>
                    )}
                  </span>
                  <ChevronRightIcon
                    aria-hidden
                    className="size-4 shrink-0 text-muted-foreground"
                  />
                </span>
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
