import type { Artifact } from "./api"

// The formats whose spec Refine rewrites; the others keep no spec to rewrite.
const REFINABLE_FORMATS = new Set(["docx", "pdf"])

/** Whether this version can be rewritten into the next one: a finished Word
 *  or PDF document that kept its Markdown or its script. */
export function canRefine(artifact: Artifact): boolean {
  return (
    artifact.status === "ready" &&
    REFINABLE_FORMATS.has(artifact.format) &&
    artifact.spec_kind !== null
  )
}
