import { useSelection } from "@/features/models/selection/use-selection"

/** What the Refine box changes: a document's spec, or a picture. */
export type RefineSubject = "document" | "image"

/** Where Settings chooses the model each subject's edit needs. Any image model
 *  changes a picture, by editing it or drawing it again, so a picture needs one. */
export type EditModelSection = "chat-models" | "image-models"

const SLOT = { document: "text_gen", image: "image_gen" } as const

export const EDIT_MODEL_SECTION = {
  document: "chat-models",
  image: "image-models",
} as const satisfies Record<RefineSubject, EditModelSection>

// The codes the API refuses with when that slot is empty.
export const EDIT_MODEL_CODE = {
  document: "needs_chat",
  image: "needs_image",
} as const satisfies Record<RefineSubject, string>

/** Whether the model this subject's edit needs is chosen; null while that is
 *  read. Settings refreshes the read when it chooses one, so the answer follows.
 *  A failed read counts as chosen: the send's own refusal then says why. */
export function useEditModelChosen(subject: RefineSubject): boolean | null {
  const selection = useSelection(SLOT[subject])
  if (selection.isPending) return null
  if (selection.isError) return true
  return selection.data !== null
}
