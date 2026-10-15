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

export type Question =
  | { kind: "undo" }
  | { kind: "restore"; savedAt: Date; afterFailedUndo: boolean }
  | { kind: "cannot-go-back"; reason: "nothing-to-go-back-to" | "going-back-failed" }

export interface GoingBackDeps {
  options: () => Promise<GoingBackOptions>
  /** True when the backend went back; it logs why when it did not. */
  goBack: (way: Way) => Promise<boolean>
  /** True when the user agreed. A cannot-go-back notice has only Quit. */
  ask: (question: Question) => Promise<boolean>
}

export type Outcome = "restart" | "quit"

export async function offerGoingBack(deps: GoingBackDeps): Promise<Outcome> {
  const { canUndo, backupSavedAt } = await deps.options()

  if (canUndo) {
    if (!(await deps.ask({ kind: "undo" }))) return "quit"
    if (await deps.goBack("undo")) return "restart"
    if (backupSavedAt === null) return cannotGoBack(deps, "going-back-failed")
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
  if (await deps.goBack("restore")) return "restart"
  return cannotGoBack(deps, "going-back-failed")
}

async function cannotGoBack(
  deps: GoingBackDeps,
  reason: "nothing-to-go-back-to" | "going-back-failed",
): Promise<Outcome> {
  await deps.ask({ kind: "cannot-go-back", reason })
  return "quit"
}
