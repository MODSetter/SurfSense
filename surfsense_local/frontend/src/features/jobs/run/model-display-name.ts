import type { SelectableModel } from "@/features/models/chat-candidates/api"

/** A model as the chat model picker names it: its display name, else the name
 *  as sent, which is all a run's report keeps of it. */
export function displayModelName(
  name: string,
  candidates: readonly SelectableModel[] | undefined
): string {
  return (
    candidates?.find((candidate) => candidate.name === name)?.display_name ??
    name
  )
}
