import { MoveFailedError, type MoveFailure } from "./run-move.ts"

/** The window refuses to close while a move holds it, so that ends before any restart. */
export async function settleMove(
  move: Promise<void>,
  options: {
    onMovingChange: (moving: boolean) => void
    restart: () => void
    onFailed: (reason: Exclude<MoveFailure, "canceled">) => void
  },
): Promise<void> {
  const { onMovingChange, restart, onFailed } = options
  try {
    await move
    onMovingChange(false)
    restart()
  } catch (error) {
    onMovingChange(false)
    const reason = error instanceof MoveFailedError ? error.reason : "failed"
    if (reason === "canceled") restart()
    else onFailed(reason)
  }
}
