import type { FlashcardState } from "../../api"

// Pure, derived-only helpers over the server-persisted FlashcardState (see
// api.ts and backend/modules/artifacts/flashcard_progress.py) — marking,
// resetting, and shuffling are all server round-trips, so this file only
// computes things from a state, never mutates one.
export function firstUnseenCard(state: FlashcardState): number {
  for (let position = 0; position < state.order.length; position += 1) {
    if (!state.marks[String(state.order[position])]) return position
  }
  return 0
}

export function flashcardProgressCounts(state: FlashcardState, cardCount: number) {
  let remembered = 0
  let missed = 0
  for (let index = 0; index < cardCount; index += 1) {
    const mark = state.marks[String(index)]
    if (mark === "good") remembered += 1
    if (mark === "again") missed += 1
  }
  return { remembered, missed, unseen: cardCount - remembered - missed }
}
