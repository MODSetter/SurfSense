import { Fragment } from "react"

import { DotIcon } from "@/components/ui/icons"

// The backend joins a list row's details with this, such as `r/surf · u/name`.
const JOINED = " · "

/** A result's description, its details set apart by a dot icon. */
export function ResultDetails({ text }: { text: string }) {
  const parts = text.split(JOINED)
  return (
    <span className="line-clamp-2 text-sm text-muted-foreground">
      {parts.map((part, index) => (
        <Fragment key={index}>
          {index > 0 ? (
            <DotIcon
              aria-hidden="true"
              className="mx-0.5 inline size-3 align-middle"
            />
          ) : null}
          <span>{part}</span>
        </Fragment>
      ))}
    </span>
  )
}
