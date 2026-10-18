import type { ReactNode } from "react"

import { ComputerIcon } from "@/components/ui/icons"
import { Separator } from "@/components/ui/separator"
import { intl } from "@/i18n/intl"

import type { ModelType } from "../model-type"
import type { Connection } from "../remote/connections/api"
import { ChatGPTOption } from "../remote/connections/chatgpt/chatgpt-option"
import { ClaudeOption } from "../remote/connections/claude/claude-option"
import { ServerCard } from "./server-card"

/**
 * Both ways a model arrives, on one page and in the same shape for every slot:
 * the server card, then a ChatGPT plan where one fills the slot, both short,
 * then this computer's catalog, which says so itself when nothing can run here.
 */
export function AddModelOptions({
  download,
  modelType,
  onConnected,
}: {
  /** The slot's catalog for this computer. */
  download: ReactNode
  /** The slot being filled, so a ChatGPT plan is offered only where one fills it. */
  modelType: ModelType
  /** Absent where the slot offers no server. */
  onConnected?: (connection: Connection) => void
}) {
  return (
    <div className="flex flex-col gap-6">
      {onConnected ? (
        <>
          <ServerCard onConnected={onConnected} />
          <ChatGPTOption modelType={modelType} onConnected={onConnected} />
          <ClaudeOption modelType={modelType} onConnected={onConnected} />
          <Separator />
        </>
      ) : null}
      <section
        className="flex flex-col gap-3"
        aria-label={intl.formatMessage({
          id: "models_add_model_local_aria",
          defaultMessage: "On this computer",
        })}
      >
        <h3 className="flex items-center gap-2 text-base font-medium">
          <ComputerIcon
            aria-hidden="true"
            className="size-4 text-muted-foreground"
          />
          {intl.formatMessage({
            id: "models_add_model_local_title",
            defaultMessage: "On this computer",
          })}
        </h3>
        {download}
      </section>
    </div>
  )
}
