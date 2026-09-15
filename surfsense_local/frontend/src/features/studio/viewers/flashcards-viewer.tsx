import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  XIcon,
} from "@/components/ui/icons"

// The deck file's shape (schema_version 1).
export interface FlashcardDeck {
  schema_version: 1
  title: string
  cards: { front_text: string; back_text: string }[]
}

type Mark = "known" | "again"

// ponytail: the study state lives in the component; persisting marks per
// generation is a small table when a session must survive closing the panel.
export function FlashcardsViewer({ deck }: { deck: FlashcardDeck }) {
  const allCards = deck.cards.map((_, index) => index)
  const [queue, setQueue] = useState(allCards)
  const [position, setPosition] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const [marks, setMarks] = useState<Record<number, Mark>>({})

  const known = allCards.filter((card) => marks[card] === "known")
  const again = allCards.filter((card) => marks[card] === "again")
  const score = `${known.length} got it · ${again.length} again`

  const start = (cards: number[]) => {
    setQueue(cards)
    setPosition(0)
    setRevealed(false)
  }
  const goTo = (next: number) => {
    setPosition(next)
    setRevealed(false)
  }
  const mark = (value: Mark) => {
    setMarks((current) => ({ ...current, [queue[position]]: value }))
    goTo(position + 1)
  }

  if (position >= queue.length) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <p className="text-lg font-medium">
          {known.length} of {deck.cards.length} known
        </p>
        <p className="text-sm text-muted-foreground">{score}</p>
        <div className="flex gap-2">
          {again.length > 0 ? (
            <Button size="sm" onClick={() => start(again)}>
              Review {again.length} again
            </Button>
          ) : null}
          <Button variant="outline" size="sm" onClick={() => start(allCards)}>
            Start over
          </Button>
        </div>
      </div>
    )
  }

  const card = deck.cards[queue[position]]
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>
          {position + 1} / {queue.length}
        </span>
        <span>{score}</span>
      </div>
      <button
        type="button"
        aria-label={revealed ? "Answer" : "Reveal answer"}
        onClick={() => setRevealed(true)}
        className="flex min-h-48 flex-1 flex-col items-center justify-center gap-3 rounded-xl border bg-card p-6 text-center text-base"
      >
        <span className="font-medium">{card.front_text}</span>
        {revealed ? (
          <span className="border-t pt-3 text-muted-foreground">
            {card.back_text}
          </span>
        ) : null}
      </button>
      <div className="flex items-center justify-between gap-2">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Previous card"
          disabled={position === 0}
          onClick={() => goTo(position - 1)}
        >
          <ArrowLeftIcon />
        </Button>
        {revealed ? (
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => mark("again")}>
              <XIcon data-icon="inline-start" />
              Again
            </Button>
            <Button size="sm" onClick={() => mark("known")}>
              <CheckIcon data-icon="inline-start" />
              Got it
            </Button>
          </div>
        ) : null}
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Next card"
          disabled={position === queue.length - 1}
          onClick={() => goTo(position + 1)}
        >
          <ArrowRightIcon />
        </Button>
      </div>
    </div>
  )
}
