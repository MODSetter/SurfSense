import type { ReactNode } from "react"

import { ComputerIcon } from "@/components/ui/icons"
import { Separator } from "@/components/ui/separator"

import type { Connection } from "../remote/connections/api"
import { ServerCard } from "./server-card"

/**
 * Both ways a model arrives, on one page and in the same shape for every slot:
 * the server card first because it is short, then this computer's catalog,
 * which says so itself when nothing can run here.
 */
export function AddModelOptions({
  download,
  onConnected,
}: {
  /** The slot's catalog for this computer. */
  download: ReactNode
  onConnected: (connection: Connection) => void
}) {
  return (
    <div className="flex flex-col gap-6">
      <ServerCard onConnected={onConnected} />
      <Separator />
      <section className="flex flex-col gap-3" aria-label="On this computer">
        <h3 className="flex items-center gap-2 text-sm font-medium">
          <ComputerIcon
            aria-hidden="true"
            className="size-4 text-muted-foreground"
          />
          On this computer
        </h3>
        {download}
      </section>
    </div>
  )
}
