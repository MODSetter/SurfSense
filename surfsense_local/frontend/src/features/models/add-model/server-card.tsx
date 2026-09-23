import { useId, useState } from "react"

import { Button } from "@/components/ui/button"
import { ServerIcon } from "@/components/ui/icons"

import type { Connection } from "../remote/connections/api"
import { ConnectionForm } from "../remote/connections/connection-form"

/**
 * The server option, laid out like the "On this computer" section beside it.
 * Closed by default: it is short and the catalog under it is long.
 */
export function ServerCard({
  onConnected,
}: {
  onConnected: (connection: Connection) => void
}) {
  const formId = useId()
  const [open, setOpen] = useState(false)

  return (
    <section className="flex flex-col gap-3" aria-label="Use a server">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-sm font-medium">
            <ServerIcon
              aria-hidden="true"
              className="size-4 text-muted-foreground"
            />
            Use a server
          </h3>
          {/* pl-6: the icon's 16px plus the 8px gap, so it lines up with the heading text. */}
          <p className="pl-6 text-xs text-pretty text-muted-foreground">
            vLLM, LM Studio, OpenRouter or any OpenAI-compatible API.
          </p>
        </div>
        {open ? null : (
          <Button
            type="button"
            size="sm"
            variant="outline"
            aria-expanded={false}
            aria-controls={formId}
            onClick={() => setOpen(true)}
          >
            Connect
          </Button>
        )}
      </div>
      {open ? (
        <div id={formId}>
          <ConnectionForm
            onCancel={() => setOpen(false)}
            onSaved={onConnected}
          />
        </div>
      ) : null}
    </section>
  )
}
