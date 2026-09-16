import type { Quiz } from "./quiz-viewer"

// Pure, local-only quiz progress — never persisted or sent to the backend,
// so (unlike surfsense_web's server-synced quiz_state) this needs no
// generation/schema versioning: it's discarded whenever the panel unmounts.
export type QuizMode = "all" | "missed"

export interface QuizState {
  mode: QuizMode
  activeQuestionIndices: number[]
  answers: Record<number, number>
  skippedQuestionIndices: number[]
}

export function emptyQuizState(questionCount: number): QuizState {
  return {
    mode: "all",
    activeQuestionIndices: Array.from({ length: questionCount }, (_, i) => i),
    answers: {},
    skippedQuestionIndices: [],
  }
}

export function quizRunComplete(state: QuizState): boolean {
  const skipped = new Set(state.skippedQuestionIndices)
  return state.activeQuestionIndices.every(
    (index) => state.answers[index] !== undefined || skipped.has(index)
  )
}

export function firstUnansweredPosition(state: QuizState): number {
  const skipped = new Set(state.skippedQuestionIndices)
  const position = state.activeQuestionIndices.findIndex(
    (index) => state.answers[index] === undefined && !skipped.has(index)
  )
  return position < 0 ? 0 : position
}

export function quizResults(quiz: Quiz, state: QuizState) {
  const missed: number[] = []
  const skipped: number[] = []
  const skippedSet = new Set(state.skippedQuestionIndices)
  let correct = 0
  quiz.questions.forEach((question, index) => {
    if (skippedSet.has(index)) skipped.push(index)
    else if (state.answers[index] === question.correct_option_index) correct += 1
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

export function submitAnswer(
  state: QuizState,
  questionIndex: number,
  selectedOptionIndex: number
): QuizState {
  return {
    ...state,
    answers: { ...state.answers, [questionIndex]: selectedOptionIndex },
  }
}

export function skipQuestion(state: QuizState, questionIndex: number): QuizState {
  return {
    ...state,
    skippedQuestionIndices: [
      ...new Set([...state.skippedQuestionIndices, questionIndex]),
    ].sort((a, b) => a - b),
  }
}

export function retakeQuiz(
  quiz: Quiz,
  state: QuizState,
  mode: QuizMode
): QuizState {
  if (mode === "all") return emptyQuizState(quiz.questions.length)
  const result = quizResults(quiz, state)
  const missed = [...result.missed, ...result.skipped].sort((a, b) => a - b)
  const answers = { ...state.answers }
  for (const index of missed) delete answers[index]
  return {
    mode: "missed",
    activeQuestionIndices: missed,
    answers,
    skippedQuestionIndices: [],
  }
}
