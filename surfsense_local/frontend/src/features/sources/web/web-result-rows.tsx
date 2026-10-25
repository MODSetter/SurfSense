import { Fragment } from "react"

import { Separator } from "@/components/ui/separator"

import type { WebResult } from "./api"
import type { RowActions } from "./row-actions"
import { WebResultRow } from "./web-result-row"

export function WebResultRows({
  results,
  actions,
}: {
  results: WebResult[]
  actions: RowActions
}) {
  return (
    <ul className="flex flex-col">
      {results.map((result, index) => (
        <Fragment key={result.url}>
          {index > 0 ? (
            // A list holds only items; this one is drawn, not counted.
            <li role="none" aria-hidden="true">
              {/* Inset like the rows' text: full width plus margins would overflow. */}
              <Separator className="mx-3 bg-border/60 data-horizontal:w-auto" />
            </li>
          ) : null}
          <WebResultRow result={result} actions={actions} />
        </Fragment>
      ))}
    </ul>
  )
}
