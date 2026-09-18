import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useId, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { CheckIcon, XIcon } from "@/components/ui/icons"
import { Progress } from "@/components/ui/progress"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"
import {
  answerQuizQuestion,
  readArtifactFile,
  retakeQuiz as retakeQuizRequest,
  skipQuizQuestion,
  type ArtifactDetail,
  type QuizMode,
  type QuizState,
} from "../../api"
import { QuizReviewScreen } from "./review-screen"
import { QuizScoreScreen } from "./score-screen"
import { StudyText } from "../study-text"
import { VIEWER_PADDING } from "../viewer-layout"
import {
  emptyQuizState,
  firstUnansweredPosition,
  quizResults,
  quizRunComplete,
} from "./state"

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

// Fetches the quiz's questions; the run's progress (answers, skips, mode)
// comes from the artifact itself (artifact.quiz_state), already persisted
// server-side — see backend/modules/artifacts/quiz_progress.py.
export function QuizViewer({ artifact }: { artifact: ArtifactDetail }) {
  const { data: quiz, isLoading, error } = useQuery({
    queryKey: ["artifact-file", artifact.id],
    queryFn: ({ signal }) => readArtifactFile<Quiz>(artifact.id, signal),
  })

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <Spinner />
      </div>
    )
  }
  if (error || !quiz) {
    return (
      <p className={`${VIEWER_PADDING} text-destructive text-sm`}>
        {error instanceof Error ? error.message : "Failed to load this quiz"}
      </p>
    )
  }
  return <QuizRunner artifact={artifact} quiz={quiz} />
}

function QuizRunner({
  artifact,
  quiz,
}: {
  artifact: ArtifactDetail
  quiz: Quiz
}) {
  const queryClient = useQueryClient()
  const headingId = useId()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [state, setState] = useState<QuizState>(
    () =>
      artifact.quiz_state ??
      emptyQuizState(artifact.generation, quiz.questions.length)
  )
  const [screen, setScreen] = useState<Screen>(() =>
    quizRunComplete(state) ? "score" : "taking"
  )
  const [position, setPosition] = useState(() => firstUnansweredPosition(state))
  const [reviewIndex, setReviewIndex] = useState(0)
  const [selectedOption, setSelectedOption] = useState<number | null>(null)
  const [message, setMessage] = useState("")

  const answer = useMutation({
    mutationFn: (body: { question_index: number; selected_option_index: number }) =>
      answerQuizQuestion(artifact.id, body),
  })
  const skip = useMutation({
    mutationFn: (body: { question_index: number }) =>
      skipQuizQuestion(artifact.id, body),
  })
  const retake = useMutation({
    mutationFn: (body: { mode: QuizMode }) => retakeQuizRequest(artifact.id, body),
  })
  const saving = answer.isPending || skip.isPending

  // A mutation's returned state is the source of truth from here on; caching
  // it keeps the next GET (a regenerate, a re-open) from showing stale
  // progress the artifact query hasn't refetched yet.
  function applyState(next: QuizState) {
    setState(next)
    queryClient.setQueryData(
      ["artifact", artifact.id],
      (current: ArtifactDetail | undefined) =>
        current && { ...current, quiz_state: next }
    )
  }

  const results = quizResults(quiz, state)
  const questionIndex = state.active_question_indices[position] ?? 0
  const question = quiz.questions[questionIndex]
  const submittedOption = state.answers[questionIndex]
  const answerRevealed = submittedOption !== undefined
  const isLastQuestion = position === state.active_question_indices.length - 1

  async function selectAnswer(optionIndex: number) {
    if (answerRevealed || saving) return
    setMessage("")
    try {
      const next = await answer.mutateAsync({
        question_index: questionIndex,
        selected_option_index: optionIndex,
      })
      applyState(next)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Answer could not be saved")
    }
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

  async function skipQuestion() {
    if (answerRevealed || saving) return
    setMessage("")
    try {
      const next = await skip.mutateAsync({ question_index: questionIndex })
      applyState(next)
      moveForward()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Question could not be skipped")
    }
  }

  async function startRetake(mode: QuizMode) {
    if (retake.isPending) return
    setMessage("")
    try {
      const next = await retake.mutateAsync({ mode })
      applyState(next)
      setPosition(firstUnansweredPosition(next))
      setSelectedOption(null)
      setScreen(quizRunComplete(next) ? "score" : "taking")
      requestAnimationFrame(() => headingRef.current?.focus())
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Quiz could not be restarted")
    }
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
          {position + 1} / {state.active_question_indices.length}
        </p>
      </div>
      <Progress
        value={
          ((position + (answerRevealed ? 1 : 0)) /
            state.active_question_indices.length) *
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
        <StudyText content={question.question_text} />
      </h2>
      <RadioGroup
        value={selectedOption === null ? "" : String(selectedOption)}
        onValueChange={(value) => {
          setSelectedOption(Number(value))
          void selectAnswer(Number(value))
        }}
        disabled={answerRevealed || saving}
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
                <StudyText content={option} />
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
          disabled={saving}
          onClick={answerRevealed ? moveForward : () => void skipQuestion()}
        >
          {answerRevealed ? (isLastQuestion ? "Finish" : "Next") : "Skip"}
        </Button>
      </div>
      {message ? (
        <p role="alert" className="mt-4 text-destructive text-sm">
          {message}
        </p>
      ) : null}
    </section>
  )
}
