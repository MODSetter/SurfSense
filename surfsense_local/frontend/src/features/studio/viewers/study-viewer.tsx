import { useQuery } from "@tanstack/react-query"

import { Spinner } from "@/components/ui/spinner"
import { readArtifactFile } from "../api"
import { FlashcardsViewer, type FlashcardDeck } from "./flashcards-viewer"
import { QuizViewer, type Quiz } from "./quiz-viewer"

// Flashcards and quizzes study from their JSON primary, not the markdown body.
export function StudyViewer({
  artifactId,
  format,
}: {
  artifactId: number
  format: "flashcards" | "quiz"
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["artifact-file", artifactId],
    queryFn: ({ signal }) =>
      readArtifactFile<FlashcardDeck | Quiz>(artifactId, signal),
  })

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <Spinner />
      </div>
    )
  }
  if (error || !data) {
    return (
      <p className="text-sm text-destructive">
        {error instanceof Error
          ? error.message
          : "Failed to load this artifact"}
      </p>
    )
  }
  return format === "quiz" ? (
    <QuizViewer quiz={data as Quiz} />
  ) : (
    <FlashcardsViewer deck={data as FlashcardDeck} />
  )
}
