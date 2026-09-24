import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { createPortal } from "react-dom"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  RefreshCwIcon,
  ShuffleIcon,
} from "@/components/ui/icons"
import { Progress } from "@/components/ui/progress"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import {
  markFlashcard,
  readArtifactFile,
  reorderFlashcards,
  resetFlashcardProgress,
  type ArtifactDetail,
  type FlashcardMark,
  type FlashcardState,
} from "../../api"
import { shuffledCardOrder } from "./card-order"
import { FlashcardSurface } from "./flashcard-surface"
import { firstUnseenCard, flashcardProgressCounts } from "./state"
import { StudyText } from "../study-text"
import { VIEWER_PADDING } from "../viewer-layout"

// The deck file's shape (schema_version 1).
export interface FlashcardDeck {
  schema_version: 1
  title: string
  cards: { front_text: string; back_text: string }[]
}

// Fetches the deck's cards; the study progress (marks, shuffle order) comes
// from the artifact itself (artifact.flashcard_state), already persisted
// server-side — see backend/modules/artifacts/flashcard_progress.py.
export function FlashcardsViewer({
  artifact,
  actionsContainer,
}: {
  artifact: ArtifactDetail
  actionsContainer: HTMLElement | null
}) {
  const {
    data: deck,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["artifact-file", artifact.id],
    queryFn: ({ signal }) =>
      readArtifactFile<FlashcardDeck>(artifact.id, signal),
  })

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <Spinner />
      </div>
    )
  }
  if (error || !deck) {
    return (
      <p className={`${VIEWER_PADDING} text-sm text-destructive`}>
        {error instanceof Error
          ? error.message
          : intl.formatMessage({ id: "studio_flashcards_viewer_load_error" })}
      </p>
    )
  }
  return (
    <FlashcardRunner
      artifact={artifact}
      deck={deck}
      actionsContainer={actionsContainer}
    />
  )
}

function FlashcardRunner({
  artifact,
  deck,
  actionsContainer,
}: {
  artifact: ArtifactDetail
  deck: FlashcardDeck
  actionsContainer: HTMLElement | null
}) {
  const queryClient = useQueryClient()
  const [state, setState] = useState<FlashcardState>(
    () =>
      artifact.flashcard_state ?? {
        generation: artifact.generation,
        marks: {},
        order: deck.cards.map((_, index) => index),
      }
  )
  const [currentIndex, setCurrentIndex] = useState(() => firstUnseenCard(state))
  const [revealed, setRevealed] = useState(false)
  const [message, setMessage] = useState("")

  const mark = useMutation({
    mutationFn: (body: { card_index: number; mark: FlashcardMark | null }) =>
      markFlashcard(artifact.id, body),
  })
  const reorder = useMutation({
    mutationFn: (body: { order: number[] }) =>
      reorderFlashcards(artifact.id, body),
  })
  const reset = useMutation({
    mutationFn: () => resetFlashcardProgress(artifact.id),
  })
  const saving = mark.isPending || reorder.isPending || reset.isPending

  function applyState(next: FlashcardState) {
    setState(next)
    queryClient.setQueryData(
      ["artifact", artifact.id],
      (current: ArtifactDetail | undefined) =>
        current && { ...current, flashcard_state: next }
    )
  }

  const cardIndex = state.order[currentIndex] ?? currentIndex
  const card = deck.cards[cardIndex]
  const counts = flashcardProgressCounts(state, deck.cards.length)
  const currentMark = state.marks[String(cardIndex)]

  function move(offset: number) {
    const next = currentIndex + offset
    if (next < 0 || next >= deck.cards.length) return
    setCurrentIndex(next)
    setRevealed(false)
  }

  async function markCard(value: FlashcardMark) {
    if (saving) return
    setMessage("")
    const next = currentIndex + 1
    try {
      const authoritative = await mark.mutateAsync({
        card_index: cardIndex,
        mark: value,
      })
      applyState(authoritative)
      if (next < deck.cards.length) {
        setCurrentIndex(next)
        setRevealed(false)
      }
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : intl.formatMessage({ id: "studio_flashcards_viewer_mark_error" })
      )
    }
  }

  async function shuffle() {
    if (saving) return
    setMessage("")
    const order = shuffledCardOrder(deck.cards.length)
    try {
      const next = await reorder.mutateAsync({ order })
      applyState(next)
      setCurrentIndex(0)
      setRevealed(false)
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : intl.formatMessage({ id: "studio_flashcards_viewer_shuffle_error" })
      )
    }
  }

  async function resetProgress() {
    if (saving) return
    setMessage("")
    try {
      applyState(await reset.mutateAsync())
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : intl.formatMessage({ id: "studio_flashcards_viewer_reset_error" })
      )
    }
  }

  const progressValue = ((currentIndex + 1) / deck.cards.length) * 100
  const faceClass =
    "relative mx-auto flex h-full max-w-md flex-col justify-center"
  const hasProgress = Object.keys(state.marks).length > 0

  return (
    <div className={`flex h-full flex-col gap-4 ${VIEWER_PADDING}`}>
      {actionsContainer
        ? createPortal(
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  disabled={!hasProgress || saving}
                  aria-label={intl.formatMessage({
                    id: "studio_flashcards_viewer_reset_aria",
                  })}
                >
                  <RefreshCwIcon />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>
                    {intl.formatMessage({
                      id: "studio_flashcards_reset_dialog_title",
                    })}
                  </AlertDialogTitle>
                  <AlertDialogDescription>
                    {intl.formatMessage({
                      id: "studio_flashcards_reset_dialog_body",
                    })}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>
                    {intl.formatMessage({
                      id: "studio_flashcards_reset_dialog_cancel_button",
                    })}
                  </AlertDialogCancel>
                  <AlertDialogAction onClick={() => void resetProgress()}>
                    {intl.formatMessage({
                      id: "studio_flashcards_reset_dialog_confirm_button",
                    })}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>,
            actionsContainer
          )
        : null}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <p className="truncate">{deck.title}</p>
        <p className="shrink-0 tabular-nums">
          {intl.formatMessage(
            { id: "studio_flashcards_viewer_remaining_status" },
            {
              count: counts.unseen,
            }
          )}
        </p>
      </div>

      <div className="aspect-[28/17] w-full shrink-0">
        <FlashcardSurface
          revealed={revealed}
          onFlip={() => setRevealed((current) => !current)}
          front={
            <div className={faceClass}>
              <p className="absolute top-0 left-0 text-xs text-muted-foreground tabular-nums">
                {currentIndex + 1} / {deck.cards.length}
              </p>
              <p className="mb-4 text-xs font-medium tracking-wider text-muted-foreground uppercase">
                {intl.formatMessage({
                  id: "studio_flashcards_card_question_label",
                })}
              </p>
              <StudyText
                content={card.front_text}
                className="text-sm sm:text-base lg:text-lg"
              />
              <p
                aria-hidden="true"
                className="absolute inset-x-0 -bottom-5 text-center text-xs text-muted-foreground"
              >
                {intl.formatMessage({
                  id: "studio_flashcards_card_see_answer_body",
                })}
              </p>
            </div>
          }
          back={
            <div className={faceClass}>
              <p className="absolute top-0 left-0 text-xs text-muted-foreground tabular-nums">
                {currentIndex + 1} / {deck.cards.length}
              </p>
              <p className="mb-4 text-xs font-medium tracking-wider text-muted-foreground uppercase">
                {intl.formatMessage({
                  id: "studio_flashcards_card_answer_label",
                })}
              </p>
              <StudyText
                content={card.back_text}
                className="text-sm sm:text-base lg:text-lg"
              />
              {currentMark ? (
                <p className="mt-6 text-xs font-medium text-muted-foreground">
                  {currentMark === "good"
                    ? intl.formatMessage({
                        id: "studio_flashcards_card_mark_good_body",
                      })
                    : intl.formatMessage({
                        id: "studio_flashcards_card_mark_again_body",
                      })}
                </p>
              ) : null}
            </div>
          }
        />
      </div>

      <Progress
        value={progressValue}
        className="h-1.5"
        role="progressbar"
        aria-label={intl.formatMessage({
          id: "studio_flashcards_viewer_progress_aria",
        })}
      />

      <div className="flex items-center justify-center gap-4 sm:gap-6">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          disabled={currentIndex === 0}
          onClick={() => move(-1)}
          aria-label={intl.formatMessage({
            id: "studio_flashcards_viewer_previous_aria",
          })}
        >
          <ArrowLeftIcon />
        </Button>
        <div className="flex min-w-0 items-center justify-center gap-2">
          <Button
            type="button"
            size="sm"
            className="gap-2 bg-destructive/80 text-white hover:bg-destructive"
            disabled={saving}
            onClick={() => void markCard("again")}
            aria-label={intl.formatMessage(
              { id: "studio_flashcards_viewer_again_aria" },
              {
                count: counts.missed,
              }
            )}
          >
            <span className="tabular-nums">{counts.missed}</span>
            <span className="hidden sm:inline">
              {intl.formatMessage({
                id: "studio_flashcards_viewer_again_button",
              })}
            </span>
          </Button>
          <Button
            type="button"
            size="sm"
            className="gap-2 bg-emerald-700 text-white hover:bg-emerald-800"
            disabled={saving}
            onClick={() => void markCard("good")}
            aria-label={intl.formatMessage(
              { id: "studio_flashcards_viewer_good_aria" },
              {
                count: counts.remembered,
              }
            )}
          >
            <span className="tabular-nums">{counts.remembered}</span>
            <span className="hidden sm:inline">
              {intl.formatMessage({
                id: "studio_flashcards_viewer_good_button",
              })}
            </span>
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={saving}
            onClick={() => void shuffle()}
            aria-label={intl.formatMessage({
              id: "studio_flashcards_viewer_shuffle_aria",
            })}
          >
            <ShuffleIcon data-icon="inline-start" />
            <span className="hidden sm:inline">
              {intl.formatMessage({
                id: "studio_flashcards_viewer_shuffle_button",
              })}
            </span>
          </Button>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          disabled={currentIndex === deck.cards.length - 1}
          onClick={() => move(1)}
          aria-label={intl.formatMessage({
            id: "studio_flashcards_viewer_next_aria",
          })}
        >
          <ArrowRightIcon />
        </Button>
      </div>
      {message ? (
        <p role="alert" className="text-center text-sm text-destructive">
          {message}
        </p>
      ) : null}
    </div>
  )
}
