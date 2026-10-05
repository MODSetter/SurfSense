import type { Artifact } from "./api"

/** Whether this version can be rewritten into the next one: a finished Word
 *  or PDF document Studio made. The agent's own documents are edited in its
 *  chat (07-create-and-edit-mvp, decision 8), so the API says which. */
export function canRefine(artifact: Artifact): boolean {
  return artifact.refinable
}
