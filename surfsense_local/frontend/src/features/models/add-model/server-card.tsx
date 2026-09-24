import { useState } from "react"

import { Button } from "@/components/ui/button"
import { ServerIcon } from "@/components/ui/icons"

import type { Connection } from "../remote/connections/api"
import { ConnectionDialog } from "../remote/connections/connection-dialog"

/**
 * The server option, laid out like the "On this computer" section beside it.
 * Connecting happens in a dialog; a new server is handed up, so the page
 * can show its models.
 */
export function ServerCard({
  onConnected,
}: {
  onConnected: (connection: Connection) => void
}) {
  const [connecting, setConnecting] = useState(false)

  return (
    <section className="flex flex-col gap-3" aria-label="Use a server">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-base font-medium">
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
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setConnecting(true)}
        >
          Connect
        </Button>
      </div>
      <ConnectionDialog
        open={connecting}
        onOpenChange={setConnecting}
        onCreated={onConnected}
      />
    </section>
  )
}
