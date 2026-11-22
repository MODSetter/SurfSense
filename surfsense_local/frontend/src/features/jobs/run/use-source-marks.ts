import { useState } from "react"

/** The sources the user ticked or unticked in a run form, each kept over the
 *  sidebar's choice for it. */
export function useSourceMarks() {
  const [marks, setMarks] = useState<ReadonlyMap<number, boolean>>(new Map())
  const mark = (documentIds: readonly number[], on: boolean) =>
    setMarks(
      (current) =>
        new Map([...current, ...documentIds.map((id) => [id, on] as const)])
    )
  return [marks, mark] as const
}
