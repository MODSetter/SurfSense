import type { QuizState } from "../../api"
import type { Quiz } from "./quiz-viewer"

// Pure, derived-only helpers over the server-persisted QuizState (see
// api.ts and backend/modules/artifacts/quiz_progress.py) — answering,
// skipping, and retaking are all server round-trips now, so this file only
// computes things from a state, never mutates one.
export function emptyQuizState(
  generation: number,
  questionCount: number
): QuizState {
  return {
    generation,
    mode: "all",
    active_question_indices: Array.from({ length: questionCount }, (_, i) => i),
    answers: {},
    skipped_question_indices: [],
  }
}

export function quizRunComplete(state: QuizState): boolean {
  const skipped = new Set(state.skipped_question_indices)
  return state.active_question_indices.every(
    (index) => state.answers[index] !== undefined || skipped.has(index)
  )
}

export function firstUnansweredPosition(state: QuizState): number {
  const skipped = new Set(state.skipped_question_indices)
  const position = state.active_question_indices.findIndex(
    (index) => state.answers[index] === undefined && !skipped.has(index)
  )
  return position < 0 ? 0 : position
}

export function quizResults(quiz: Quiz, state: QuizState) {
  const missed: number[] = []
  const skipped: number[] = []
  const skippedSet = new Set(state.skipped_question_indices)
  let correct = 0
  quiz.questions.forEach((question, index) => {
    if (skippedSet.has(index)) skipped.push(index)
    else if (state.answers[index] === question.correct_option_index)
      correct += 1
    else missed.push(index)
  })
  return {
    correct,
    missed,
    skipped,
    total: quiz.questions.length,
    percentage: quiz.questions.length
      ? Math.round((correct / quiz.questions.length) * 100)
      : 0,
  }
}
