/**
 * What to offer when the API refused a database a newer release upgraded.
 * Nothing changes the data until the user agrees.
 */

export type Way = "undo" | "restore"

export interface GoingBackOptions {
  /** The newer release left undo steps that reach back to this one. */
  canUndo: boolean
  /** When the copy from before the update was saved; null when none opens here. */
  backupSavedAt: Date | null
}

/** A failure is "unchanged" only when the backend loaded the set-aside copy back. */
export type GoBackResult = "went-back" | "failed-data-unchanged" | "failed-data-may-have-changed"

type CannotGoBackReason = "nothing-to-go-back-to" | Exclude<GoBackResult, "went-back">

export type Question =
  | { kind: "undo" }
  | { kind: "restore"; savedAt: Date; afterFailedUndo: boolean }
  | { kind: "cannot-go-back"; reason: CannotGoBackReason }

export interface GoingBackDeps {
  options: () => Promise<GoingBackOptions>
  /** The backend logs why when it did not go back. */
  goBack: (way: Way) => Promise<GoBackResult>
  /** True when the user agreed. A cannot-go-back notice has only Quit. */
  ask: (question: Question) => Promise<boolean>
}

export type Outcome = "restart" | "quit"

export async function offerGoingBack(deps: GoingBackDeps): Promise<Outcome> {
  const { canUndo, backupSavedAt } = await deps.options()

  if (canUndo) {
    if (!(await deps.ask({ kind: "undo" }))) return "quit"
    const undone = await deps.goBack("undo")
    if (undone === "went-back") return "restart"
    if (backupSavedAt === null) return cannotGoBack(deps, undone)
    return offerRestore(deps, backupSavedAt, true)
  }
  if (backupSavedAt !== null) return offerRestore(deps, backupSavedAt, false)
  return cannotGoBack(deps, "nothing-to-go-back-to")
}

async function offerRestore(
  deps: GoingBackDeps,
  savedAt: Date,
  afterFailedUndo: boolean,
): Promise<Outcome> {
  if (!(await deps.ask({ kind: "restore", savedAt, afterFailedUndo }))) return "quit"
  const restored = await deps.goBack("restore")
  if (restored === "went-back") return "restart"
  return cannotGoBack(deps, restored)
}

async function cannotGoBack(deps: GoingBackDeps, reason: CannotGoBackReason): Promise<Outcome> {
  await deps.ask({ kind: "cannot-go-back", reason })
  return "quit"
}
