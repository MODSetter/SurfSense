import type { Artifact } from "./api"

/** Whether this version can be rewritten into the next one: a finished Word
 *  or PDF document Studio made, or a web page a model wrote there (not one
 *  from the template). The agent's own documents and pages are edited in its
 *  chat (07-create-and-edit-mvp, decision 8), so the API says which. */
export function canRefine(artifact: Artifact): boolean {
  return artifact.refinable
}
