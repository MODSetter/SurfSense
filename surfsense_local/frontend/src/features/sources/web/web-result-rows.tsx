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
      {results.map((result) => (
        <WebResultRow key={result.url} result={result} actions={actions} />
      ))}
    </ul>
  )
}
