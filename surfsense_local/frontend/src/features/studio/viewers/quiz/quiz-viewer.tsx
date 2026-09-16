import { useId, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { CheckIcon, XIcon } from "@/components/ui/icons"
import { Progress } from "@/components/ui/progress"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { cn } from "@/lib/utils"
import {
  emptyQuizState,
  firstUnansweredPosition,
  type QuizMode,
  type QuizState,
  quizResults,
  quizRunComplete,
  retakeQuiz,
  skipQuestion,
  submitAnswer,
} from "./state"
import { QuizReviewScreen } from "./review-screen"
import { QuizScoreScreen } from "./score-screen"
import { VIEWER_PADDING } from "../viewer-layout"

// The quiz file's shape (schema_version 1).
export interface Quiz {
  schema_version: 1
  title: string
  questions: {
    question_text: string
    options: string[]
    correct_option_index: number
    explanation_text: string
  }[]
}

const OPTION_LABELS = ["A", "B", "C", "D"] as const
type Screen = "taking" | "score" | "review"

// Local-only study state (see state.ts): nothing here is persisted, so
// closing and reopening the panel restarts the quiz — same tradeoff the
// previous version of this viewer made.
export function QuizViewer({ quiz }: { quiz: Quiz }) {
  const headingId = useId()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [state, setState] = useState<QuizState>(() =>
    emptyQuizState(quiz.questions.length)
  )
  const [screen, setScreen] = useState<Screen>("taking")
  const [position, setPosition] = useState(0)
  const [reviewIndex, setReviewIndex] = useState(0)
  const [selectedOption, setSelectedOption] = useState<number | null>(null)

  const results = quizResults(quiz, state)
  const questionIndex = state.activeQuestionIndices[position] ?? 0
  const question = quiz.questions[questionIndex]
  const submittedOption = state.answers[questionIndex]
  const answerRevealed = submittedOption !== undefined
  const isLastQuestion = position === state.activeQuestionIndices.length - 1

  function selectAnswer(optionIndex: number) {
    if (answerRevealed) return
    setSelectedOption(optionIndex)
    setState((current) => submitAnswer(current, questionIndex, optionIndex))
  }

  function moveForward() {
    setSelectedOption(null)
    if (isLastQuestion) {
      setScreen("score")
    } else {
      setPosition((current) => current + 1)
      requestAnimationFrame(() => headingRef.current?.focus())
    }
  }

  function skip() {
    if (answerRevealed) return
    const next = skipQuestion(state, questionIndex)
    setState(next)
    moveForward()
  }

  function startRetake(mode: QuizMode) {
    const next = retakeQuiz(quiz, state, mode)
    setState(next)
    setPosition(firstUnansweredPosition(next))
    setSelectedOption(null)
    setScreen(quizRunComplete(next) ? "score" : "taking")
    requestAnimationFrame(() => headingRef.current?.focus())
  }

  if (screen === "score") {
    return (
      <div className={VIEWER_PADDING}>
        <QuizScoreScreen
          quiz={quiz}
          correct={results.correct}
          missed={results.missed}
          skipped={results.skipped}
          percentage={results.percentage}
          onReview={(index) => {
            setReviewIndex(index)
            setScreen("review")
          }}
          onRetake={startRetake}
        />
      </div>
    )
  }

  if (screen === "review") {
    return (
      <div className={VIEWER_PADDING}>
        <QuizReviewScreen
          quiz={quiz}
          state={state}
          index={reviewIndex}
          onIndexChange={setReviewIndex}
          onExit={() => setScreen("score")}
        />
      </div>
    )
  }

  return (
    <section aria-labelledby={headingId} className={VIEWER_PADDING}>
      <div className="mb-6 flex items-center justify-between gap-4 text-muted-foreground text-sm">
        <p className="truncate">Attempt your quiz</p>
        <p className="shrink-0 tabular-nums">
          {position + 1} / {state.activeQuestionIndices.length}
        </p>
      </div>
      <Progress
        value={
          ((position + (answerRevealed ? 1 : 0)) /
            state.activeQuestionIndices.length) *
          100
        }
        className="mb-8 h-1.5"
        role="progressbar"
        aria-label="Quiz progress"
      />
      <h2
        id={headingId}
        ref={headingRef}
        tabIndex={-1}
        className="mb-6 font-semibold text-xl outline-none sm:text-2xl"
      >
        {question.question_text}
      </h2>
      <RadioGroup
        value={selectedOption === null ? "" : String(selectedOption)}
        onValueChange={(value) => selectAnswer(Number(value))}
        disabled={answerRevealed}
        aria-label={`Question ${questionIndex + 1} options`}
        className="gap-3"
      >
        {question.options.map((option, index) => {
          const optionId = `${headingId}-option-${index}`
          const isCorrect = index === question.correct_option_index
          const isSubmitted = index === submittedOption
          return (
            <label
              key={optionId}
              htmlFor={optionId}
              className={cn(
                "flex min-h-14 items-center gap-3 rounded-xl border p-4 transition-colors",
                answerRevealed
                  ? "cursor-default"
                  : "cursor-pointer hover:border-foreground/25 hover:bg-muted/50",
                answerRevealed && isCorrect && "border-emerald-600",
                answerRevealed &&
                  isSubmitted &&
                  !isCorrect &&
                  "border-destructive",
                !answerRevealed && selectedOption === index && "border-primary"
              )}
            >
              <RadioGroupItem id={optionId} value={String(index)} />
              <span className="flex min-w-0 flex-1 gap-3">
                <span className="font-medium text-muted-foreground">
                  {OPTION_LABELS[index]}.
                </span>
                <span>{option}</span>
              </span>
              {answerRevealed && isCorrect ? (
                <span className="text-emerald-600">
                  <CheckIcon className="size-5" />
                  <span className="sr-only">Correct answer</span>
                </span>
              ) : answerRevealed && isSubmitted ? (
                <span className="text-destructive">
                  <XIcon className="size-5" />
                  <span className="sr-only">Incorrect answer</span>
                </span>
              ) : null}
            </label>
          )
        })}
      </RadioGroup>
      <div className="mt-6 flex justify-end">
        <Button
          type="button"
          onClick={answerRevealed ? moveForward : skip}
        >
          {answerRevealed ? (isLastQuestion ? "Finish" : "Next") : "Skip"}
        </Button>
      </div>
    </section>
  )
}
