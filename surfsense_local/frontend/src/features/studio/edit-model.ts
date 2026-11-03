import { useSelection } from "@/features/models/selection/use-selection"

/** What the Refine box changes: a document's spec, or a picture. */
export type RefineSubject = "document" | "image"

/** Where Settings chooses the model each subject's edit needs. */
export type EditModelSection = "chat-models" | "image-edit-models"

const SLOT = { document: "text_gen", image: "image_edit" } as const

export const EDIT_MODEL_SECTION = {
  document: "chat-models",
  image: "image-edit-models",
} as const satisfies Record<RefineSubject, EditModelSection>

// The codes the API refuses with when that slot is empty.
export const EDIT_MODEL_CODE = {
  document: "needs_chat",
  image: "needs_image_edit",
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
