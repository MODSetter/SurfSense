import { useMutation, useQuery } from "@tanstack/react-query"
import { useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { ChevronRightIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import type { AgentStep } from "@/features/agent/api"
import { readStepResult } from "@/features/agent/api"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import { savePluginStep } from "../api"
import { usePluginOfStep } from "./plugin-of-step"

function stepName(found: ReturnType<typeof usePluginOfStep>) {
  if (!found) return null
  return intl.formatMessage(
    {
      id: "plugins_step_label",
      defaultMessage: "{plugin}: {tool}",
    },
    {
      plugin: found.plugin.name,
      tool: found.tool.title ?? found.tool.name,
    }
  )
}

/**
 * A plugin's step: named by its plugin and tool, its whole result read when
 * opened, and the result kept as a note on request. `fallback` is the line
 * any other step draws, for a plugin since disconnected.
 */
export function PluginStepLine({
  step,
  threadId,
  status,
  fallback,
  ask,
}: {
  step: AgentStep
  threadId: number
  status: ReactNode
  fallback: ReactNode
  /** A request the step waits on, shown under it. */
  ask?: ReactNode
}) {
  const found = usePluginOfStep(step.tool)
  const [open, setOpen] = useState(false)
  const result = useQuery({
    queryKey: ["step-result", threadId, step.id],
    queryFn: ({ signal }) => readStepResult(threadId, step.id, signal),
    enabled: open && step.status !== "running",
    staleTime: Infinity,
  })
  const save = useMutation({
    mutationFn: () => savePluginStep(threadId, step.id),
  })
  const detail =
    result.data?.error ?? result.data?.output ?? step.error ?? step.output
  const saved = save.isSuccess

  return (
    <li className="py-0.5">
      <details
        className="group"
        onToggle={(event) => setOpen(event.currentTarget.open)}
      >
        <summary className="flex cursor-pointer list-none items-center gap-1 rounded-sm outline-none select-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
          <span className="flex min-w-0 items-center gap-2">
            {status}
            <span className="min-w-0 truncate">
              {stepName(found) ?? fallback}
            </span>
          </span>
          <ChevronRightIcon className="size-3.5 shrink-0 transition-transform duration-150 group-open:rotate-90 motion-reduce:transition-none" />
        </summary>
        <div className="mt-1 ml-5.5 flex flex-col gap-1.5">
          {detail ? (
            <pre
              className={cn(
                "max-h-72 overflow-auto rounded-md bg-muted px-3 py-2 font-mono text-xs whitespace-pre-wrap",
                step.error ? "text-destructive" : "text-foreground"
              )}
            >
              {detail}
            </pre>
          ) : null}
          {step.status === "completed" && found ? (
            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={save.isPending || saved}
                onClick={() => save.mutate()}
              >
                {save.isPending ? <Spinner data-icon="inline-start" /> : null}
                {intl.formatMessage({
                  id: "plugins_step_save_button",
                  defaultMessage: "Save to Sources",
                })}
              </Button>
              {saved ? (
                <span role="status" className="text-xs">
                  {intl.formatMessage({
                    id: "plugins_step_saved_status",
                    defaultMessage: "Saved to Sources",
                  })}
                </span>
              ) : null}
              {save.isError ? (
                <span role="alert" className="text-xs text-destructive">
                  {intl.formatMessage({
                    id: "plugins_step_save_error",
                    defaultMessage: "Couldn’t save this result.",
                  })}
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
      </details>
      {ask}
    </li>
  )
}
