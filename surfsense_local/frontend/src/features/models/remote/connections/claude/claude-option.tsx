import { useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { ClaudeIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { ModelType } from "../../../model-type"
import { useRefreshModels } from "../../../models-query"
import type { Connection } from "../api"
import { useConnectionsServing } from "../use-connections"
import { claudeOptionQueryKey, getClaudeOption } from "./api"
import { ClaudeDialog } from "./claude-dialog"

/**
 * A Claude plan, offered beside the ChatGPT plan: it runs the user's own
 * Claude Code, so setting it up is a dialog that says what Claude Code needs.
 * Shown only where the backend says a plan fills the slot; one already
 * connected opens its models instead.
 */
export function ClaudeOption({
  modelType,
  onConnected,
  dense = false,
}: {
  modelType: ModelType
  onConnected: (connection: Connection) => void
  /** Onboarding's smaller heading and button, beside its own server row. */
  dense?: boolean
}) {
  const option = useQuery({
    queryKey: claudeOptionQueryKey,
    queryFn: ({ signal }) => getClaudeOption(signal),
    retry: false,
  })
  // The same list as the slot's, so a plan connected anywhere is reused.
  const connections = useConnectionsServing(modelType)
  const refresh = useRefreshModels()
  const [open, setOpen] = useState(false)

  if (!option.data?.serves.includes(modelType)) return null

  const connected = connections.data?.find(
    (connection) => connection.auth_kind === "claude_plan"
  )
  const size = dense ? "default" : "sm"
  const title = intl.formatMessage({
    id: "models_claude_option_title",
    defaultMessage: "Use your Claude plan",
  })

  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <div
        className={cn(
          "flex justify-between",
          dense ? "items-center gap-4" : "items-start gap-3"
        )}
      >
        <div className="min-w-0">
          <h3
            className={cn(
              "flex items-center gap-2 font-medium",
              dense ? "text-sm" : "text-base"
            )}
          >
            <ClaudeIcon
              aria-hidden="true"
              className="size-4 text-muted-foreground"
            />
            {title}
          </h3>
          {/* pl-6: the icon's 16px plus the 8px gap, so it lines up with the heading text. */}
          <p className="truncate pl-6 text-xs text-muted-foreground">
            {connected
              ? intl.formatMessage({
                  id: "models_claude_option_connected_body",
                  defaultMessage:
                    "Connected through Claude Code on this computer",
                })
              : intl.formatMessage({
                  id: "models_claude_option_body",
                  defaultMessage:
                    "Pro, Max or Team, through Claude Code on this computer.",
                })}
          </p>
        </div>
        {connected ? (
          <Button
            type="button"
            size={size}
            variant="outline"
            onClick={() => onConnected(connected)}
          >
            {intl.formatMessage({
              id: "models_claude_option_show_button",
              defaultMessage: "Show models",
            })}
          </Button>
        ) : (
          <Button
            type="button"
            size={size}
            variant="outline"
            onClick={() => setOpen(true)}
          >
            {intl.formatMessage({
              id: "models_claude_option_set_up_button",
              defaultMessage: "Set up",
            })}
          </Button>
        )}
      </div>
      <ClaudeDialog
        open={open}
        onOpenChange={setOpen}
        onConnected={(connection) => {
          void refresh()
          void connections.refetch()
          onConnected(connection)
        }}
      />
    </section>
  )
}
