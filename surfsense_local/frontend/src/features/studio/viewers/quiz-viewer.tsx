import { useState } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { VIEWER_PADDING } from "./viewer-layout"

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

// ponytail: answers live in the component; persisting them per generation
// lets a quiz survive closing the panel.
export function QuizViewer({ quiz }: { quiz: Quiz }) {
  const allQuestions = quiz.questions.map((_, index) => index)
  const [queue, setQueue] = useState(allQuestions)
  const [position, setPosition] = useState(0)
  const [answers, setAnswers] = useState<Record<number, number>>({})

  const missed = allQuestions.filter(
    (question) =>
      answers[question] !== undefined &&
      answers[question] !== quiz.questions[question].correct_option_index
  )
  const start = (questions: number[]) => {
    setQueue(questions)
    setPosition(0)
    setAnswers((current) => {
      const kept = { ...current }
      for (const question of questions) delete kept[question]
      return kept
    })
  }

  if (position >= queue.length) {
    const correct = queue.filter(
      (question) =>
        answers[question] === quiz.questions[question].correct_option_index
    ).length
    return (
      <div
        className={cn(
          "flex h-full flex-col items-center justify-center gap-3 text-center",
          VIEWER_PADDING
        )}
      >
        <p className="text-lg font-medium">
          {correct} / {queue.length} correct
        </p>
        <div className="flex gap-2">
          {missed.length > 0 ? (
            <Button size="sm" onClick={() => start(missed)}>
              Retake {missed.length} missed
            </Button>
          ) : null}
          <Button
            variant="outline"
            size="sm"
            onClick={() => start(allQuestions)}
          >
            Start over
          </Button>
        </div>
      </div>
    )
  }

  const current = queue[position]
  const question = quiz.questions[current]
  const chosen = answers[current]
  const answered = chosen !== undefined
  const isLast = position === queue.length - 1

  return (
    <div className={cn("flex h-full flex-col gap-4", VIEWER_PADDING)}>
      <p className="text-xs text-muted-foreground">
        Question {position + 1} of {queue.length}
      </p>
      <p className="text-base font-medium">{question.question_text}</p>
      <div className="flex flex-col gap-2">
        {question.options.map((option, index) => {
          const isCorrect = index === question.correct_option_index
          return (
            <Button
              key={option}
              variant="outline"
              className={cn(
                "h-auto justify-start py-2 text-left whitespace-normal",
                answered && isCorrect && "border-emerald-600",
                answered && chosen === index && !isCorrect && "border-red-600"
              )}
              disabled={answered}
              onClick={() =>
                setAnswers((all) => ({ ...all, [current]: index }))
              }
            >
              {option}
            </Button>
          )
        })}
      </div>
      {answered ? (
        <div className="space-y-2 rounded-lg bg-muted/50 p-3 text-sm">
          <p className="font-medium">
            {chosen === question.correct_option_index ? "Correct" : "Incorrect"}
          </p>
          {question.explanation_text ? (
            <p className="text-muted-foreground">{question.explanation_text}</p>
          ) : null}
          <Button size="sm" onClick={() => setPosition(position + 1)}>
            {isLast ? "See results" : "Next question"}
          </Button>
        </div>
      ) : null}
    </div>
  )
}
