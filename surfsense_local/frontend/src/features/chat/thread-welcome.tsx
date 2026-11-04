import type { ReactNode } from "react"

/** A new chat: the composer alone, centred in the conversation. */
export function ThreadWelcome({ composer }: { composer: ReactNode }) {
  return (
    <div className="flex min-h-0 flex-1">
      <div className="mx-auto grid h-full w-full max-w-3xl grid-rows-[minmax(0,1fr)_auto_minmax(0,1fr)]">
        <div />
        {composer}
      </div>
    </div>
  )
}
