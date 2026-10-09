import { useCallback, useInsertionEffect, useRef } from "react"

/**
 * A function with one identity for the component's life that calls the latest
 * `callback`, so handing it to a memoized child never re-renders that child.
 * For events and effects only: called during render it runs the last commit's.
 */
export function useStableCallback<Args extends unknown[], Result>(
  callback: (...args: Args) => Result
): (...args: Args) => Result {
  const latest = useRef(callback)
  // Before any layout effect, so a child's effect never calls a stale one.
  useInsertionEffect(() => {
    latest.current = callback
  })
  return useCallback((...args: Args) => latest.current(...args), [])
}
