import { useEffect, useRef } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  LightbulbIcon,
  XIcon,
} from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"
import type { QuizState } from "../../api"
import { StudyText } from "../study-text"
import type { Quiz } from "./quiz-viewer"

const LABELS = ["A", "B", "C", "D"] as const

export function QuizReviewScreen({
  quiz,
  state,
  index,
  onIndexChange,
  onExit,
}: {
  quiz: Quiz
  state: QuizState
  index: number
  onIndexChange: (index: number) => void
  onExit: () => void
}) {
  const question = quiz.questions[index]
  const selected = state.answers[index]
  const headingRef = useRef<HTMLHeadingElement>(null)
  useEffect(() => headingRef.current?.focus(), [])
  const moveTo = (nextIndex: number) => {
    onIndexChange(nextIndex)
    requestAnimationFrame(() => headingRef.current?.focus())
  }

  return (
    <section>
      <div className="mb-6 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">
            {intl.formatMessage({
              id: "studio_quiz_review_title",
              defaultMessage: "Review",
            })}
          </p>
          <p className="font-medium">
            {intl.formatMessage(
              {
                id: "studio_quiz_review_position_label",
                defaultMessage: "Question {number} of {total}",
              },
              {
                number: String(index + 1),
                total: String(quiz.questions.length),
              }
            )}
          </p>
        </div>
        <Button type="button" variant="secondary" size="sm" onClick={onExit}>
          {intl.formatMessage({
            id: "studio_quiz_review_exit_button",
            defaultMessage: "Exit review",
          })}
        </Button>
      </div>
      <h2
        ref={headingRef}
        tabIndex={-1}
        className="mb-6 text-xl font-semibold outline-none sm:text-2xl"
      >
        <StudyText content={question.question_text} />
      </h2>
      <div className="space-y-3">
        {question.options.map((option, optionIndex) => {
          const correct = optionIndex === question.correct_option_index
          const chosen = optionIndex === selected
          return (
            <div
              key={option}
              className={cn(
                "flex min-h-14 items-center gap-3 rounded-xl border p-4",
                correct
                  ? "border-emerald-600 bg-emerald-600/5"
                  : chosen
                    ? "border-destructive bg-destructive/5"
                    : "border-border"
              )}
            >
              <span className="font-medium text-muted-foreground">
                {LABELS[optionIndex]}.
              </span>
              <span className="min-w-0 flex-1">
                <StudyText content={option} />
              </span>
              {correct ? (
                <span className="text-emerald-600">
                  <CheckIcon className="size-5" />
                  <span className="sr-only">
                    {intl.formatMessage({
                      id: "studio_quiz_review_correct_aria",
                      defaultMessage: "Correct answer",
                    })}
                  </span>
                </span>
              ) : chosen ? (
                <span className="text-destructive">
                  <XIcon className="size-5" />
                  <span className="sr-only">
                    {intl.formatMessage({
                      id: "studio_quiz_review_incorrect_aria",
                      defaultMessage: "Incorrect answer",
                    })}
                  </span>
                </span>
              ) : null}
            </div>
          )
        })}
      </div>
      <Alert variant="secondary" className="mt-6 border-0">
        <LightbulbIcon />
        <AlertTitle>
          {intl.formatMessage({
            id: "studio_quiz_review_explanation_title",
            defaultMessage: "Explanation",
          })}
        </AlertTitle>
        <AlertDescription>
          <StudyText content={question.explanation_text} />
        </AlertDescription>
      </Alert>
      <div className="mt-6 flex items-center justify-between">
        <Button
          type="button"
          variant="ghost"
          disabled={index === 0}
          onClick={() => moveTo(index - 1)}
        >
          <ArrowLeftIcon />{" "}
          {intl.formatMessage({
            id: "studio_quiz_review_previous_button",
            defaultMessage: "Previous",
          })}
        </Button>
        <Button
          type="button"
          variant="ghost"
          disabled={index === quiz.questions.length - 1}
          onClick={() => moveTo(index + 1)}
        >
          {intl.formatMessage({
            id: "studio_quiz_review_next_button",
            defaultMessage: "Next",
          })}{" "}
          <ArrowRightIcon />
        </Button>
      </div>
    </section>
  )
}
