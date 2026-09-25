import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  ChevronDownIcon,
  ChevronRightIcon,
  RefreshCwIcon,
} from "@/components/ui/icons"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"
import type { QuizMode } from "../../api"
import { StudyText } from "../study-text"
import type { Quiz } from "./quiz-viewer"

type ResultCategory = "correct" | "missed" | "skipped"

function QuestionSection({
  title,
  indices,
  quiz,
  onReview,
}: {
  title: string
  indices: number[]
  quiz: Quiz
  onReview: (index: number) => void
}) {
  return (
    <section>
      <h3 className="text-sm font-medium">{title}</h3>
      {indices.length > 0 ? (
        <ol className="mt-2 space-y-1">
          {indices.map((index) => (
            <li key={index}>
              <button
                type="button"
                onClick={() => onReview(index)}
                aria-label={intl.formatMessage(
                  {
                    id: "studio_quiz_score_review_question_aria",
                    defaultMessage: "Review question {number, number}",
                  },
                  {
                    number: index + 1,
                  }
                )}
                className="flex w-full items-start gap-3 rounded-lg p-2 text-left text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <span className="font-medium text-foreground">
                  {intl.formatNumber(index + 1)}.
                </span>
                <span className="min-w-0 flex-1">
                  <StudyText content={quiz.questions[index].question_text} />
                </span>
                <ChevronRightIcon className="mt-0.5 size-4 shrink-0" />
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">
          {intl.formatMessage({
            id: "studio_quiz_score_section_empty",
            defaultMessage: "None",
          })}
        </p>
      )}
    </section>
  )
}

export function QuizScoreScreen({
  quiz,
  correct,
  missed,
  skipped,
  percentage,
  onReview,
  onRetake,
}: {
  quiz: Quiz
  correct: number
  missed: number[]
  skipped: number[]
  percentage: number
  onReview: (index: number) => void
  onRetake: (mode: QuizMode) => void
}) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [category, setCategory] = useState<ResultCategory>("missed")
  useEffect(() => headingRef.current?.focus(), [])
  const unresolved = new Set([...missed, ...skipped])
  const correctIndices = quiz.questions
    .map((_, index) => index)
    .filter((index) => !unresolved.has(index))
  const selectCategory = (value: string) => {
    if (value === "correct" || value === "missed" || value === "skipped") {
      setCategory(value)
    }
  }
  const questionCount = quiz.questions.length

  return (
    <section>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground">
            {intl.formatMessage({
              id: "studio_quiz_score_title",
              defaultMessage: "Your score",
            })}
          </p>
          <h2
            ref={headingRef}
            tabIndex={-1}
            className="mt-1 text-4xl font-semibold tracking-tight outline-none"
          >
            {intl.formatNumber(correct)}/
            {intl.formatNumber(quiz.questions.length)}{" "}
            <span className="text-muted-foreground">
              ({intl.formatNumber(percentage / 100, { style: "percent" })})
            </span>
          </h2>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => onReview(0)}
        >
          {intl.formatMessage({
            id: "studio_quiz_score_review_button",
            defaultMessage: "Review",
          })}
        </Button>
      </div>
      <fieldset className="mt-7 flex h-5 overflow-hidden rounded-full bg-muted">
        <legend className="sr-only">
          {intl.formatMessage({
            id: "studio_quiz_score_breakdown_aria",
            defaultMessage: "Score breakdown",
          })}
        </legend>
        <button
          type="button"
          aria-label={intl.formatMessage(
            {
              id: "studio_quiz_score_show_correct_aria",
              defaultMessage:
                "Show {count, plural, one {# correct question} other {# correct questions}}",
            },
            {
              count: correct,
            }
          )}
          onClick={() => setCategory("correct")}
          className={cn(
            "rounded-l-full border-2 border-transparent bg-emerald-600 transition-opacity hover:opacity-90",
            missed.length === 0 && skipped.length === 0 && "rounded-r-full",
            category === "correct" && "border-white"
          )}
          style={{ width: `${(correct / questionCount) * 100}%` }}
        />
        <button
          type="button"
          aria-label={intl.formatMessage(
            {
              id: "studio_quiz_score_show_missed_aria",
              defaultMessage:
                "Show {count, plural, one {# missed question} other {# missed questions}}",
            },
            {
              count: missed.length,
            }
          )}
          onClick={() => setCategory("missed")}
          className={cn(
            "border-2 border-transparent bg-red-600/40 transition-colors hover:bg-red-600/55",
            correct === 0 && "rounded-l-full",
            skipped.length === 0 && "rounded-r-full",
            category === "missed" && "border-white"
          )}
          style={{ width: `${(missed.length / questionCount) * 100}%` }}
        />
        <button
          type="button"
          aria-label={intl.formatMessage(
            {
              id: "studio_quiz_score_show_skipped_aria",
              defaultMessage:
                "Show {count, plural, one {# skipped question} other {# skipped questions}}",
            },
            {
              count: skipped.length,
            }
          )}
          onClick={() => setCategory("skipped")}
          className={cn(
            "min-w-0 flex-1 rounded-r-full border-2 border-transparent bg-muted-foreground/20 transition-colors hover:bg-muted-foreground/30",
            correct === 0 && missed.length === 0 && "rounded-l-full",
            category === "skipped" && "border-white"
          )}
        />
      </fieldset>
      <Tabs value={category} onValueChange={selectCategory} className="mt-4">
        <TabsList className="h-auto w-auto justify-center gap-0.5 bg-transparent p-0 sm:gap-2">
          <TabsTrigger
            value="correct"
            className="flex-none items-center gap-0.5 rounded-full border border-transparent px-1.5 py-1 text-xs data-[state=active]:border-transparent data-[state=active]:bg-secondary data-[state=active]:text-secondary-foreground sm:gap-1.5 sm:px-3 sm:py-1.5 sm:text-sm"
          >
            <span className="size-2 shrink-0 rounded-full bg-emerald-600 sm:size-2.5" />
            {intl.formatMessage(
              {
                id: "studio_quiz_score_correct_tab_label",
                defaultMessage: "{count, number} correct",
              },
              { count: correct }
            )}
          </TabsTrigger>
          <TabsTrigger
            value="missed"
            className="flex-none items-center gap-0.5 rounded-full border border-transparent px-1.5 py-1 text-xs data-[state=active]:border-transparent data-[state=active]:bg-secondary data-[state=active]:text-secondary-foreground sm:gap-1.5 sm:px-3 sm:py-1.5 sm:text-sm"
          >
            <span className="size-2 shrink-0 rounded-full bg-red-600 sm:size-2.5" />
            {intl.formatMessage(
              {
                id: "studio_quiz_score_missed_tab_label",
                defaultMessage: "{count, number} missed",
              },
              {
                count: missed.length,
              }
            )}
          </TabsTrigger>
          <TabsTrigger
            value="skipped"
            className="flex-none items-center gap-0.5 rounded-full border border-transparent px-1.5 py-1 text-xs data-[state=active]:border-transparent data-[state=active]:bg-secondary data-[state=active]:text-secondary-foreground sm:gap-1.5 sm:px-3 sm:py-1.5 sm:text-sm"
          >
            <span className="size-2 shrink-0 rounded-full bg-muted-foreground sm:size-2.5" />
            {intl.formatMessage(
              {
                id: "studio_quiz_score_skipped_tab_label",
                defaultMessage: "{count, number} skipped",
              },
              {
                count: skipped.length,
              }
            )}
          </TabsTrigger>
        </TabsList>
        <div className="mt-7 h-72 overflow-y-auto border-t pt-5 pr-2">
          <TabsContent value="correct" className="mt-0">
            <QuestionSection
              title={intl.formatMessage(
                {
                  id: "studio_quiz_score_correct_section_title",
                  defaultMessage: "Correct ({count, number})",
                },
                {
                  count: correctIndices.length,
                }
              )}
              indices={correctIndices}
              quiz={quiz}
              onReview={onReview}
            />
          </TabsContent>
          <TabsContent value="missed" className="mt-0">
            <QuestionSection
              title={intl.formatMessage(
                {
                  id: "studio_quiz_score_missed_section_title",
                  defaultMessage: "Missed ({count, number})",
                },
                {
                  count: missed.length,
                }
              )}
              indices={missed}
              quiz={quiz}
              onReview={onReview}
            />
          </TabsContent>
          <TabsContent value="skipped" className="mt-0">
            <QuestionSection
              title={intl.formatMessage(
                {
                  id: "studio_quiz_score_skipped_section_title",
                  defaultMessage: "Skipped ({count, number})",
                },
                {
                  count: skipped.length,
                }
              )}
              indices={skipped}
              quiz={quiz}
              onReview={onReview}
            />
          </TabsContent>
        </div>
      </Tabs>
      <div className="mt-7 flex justify-end border-t pt-5">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" variant="secondary">
              <RefreshCwIcon />{" "}
              {intl.formatMessage({
                id: "studio_quiz_score_retake_button",
                defaultMessage: "Retake quiz",
              })}{" "}
              <ChevronDownIcon />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem
              disabled={missed.length + skipped.length === 0}
              onSelect={() => onRetake("missed")}
            >
              {intl.formatMessage({
                id: "studio_quiz_score_retake_missed_label",
                defaultMessage: "Retake missed questions",
              })}
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => onRetake("all")}>
              {intl.formatMessage({
                id: "studio_quiz_score_retake_all_label",
                defaultMessage: "Retake all questions",
              })}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </section>
  )
}
