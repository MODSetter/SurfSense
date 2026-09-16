import { useQuery } from "@tanstack/react-query"

import { Spinner } from "@/components/ui/spinner"
import { readArtifactFile } from "../api"
import { FlashcardsViewer, type FlashcardDeck } from "./flashcards-viewer"
import { VIEWER_PADDING } from "./viewer-layout"

// Flashcards study from their JSON primary, not the markdown body. (Quiz
// used to share this viewer too, but it now self-fetches — see
// quiz/quiz-viewer.tsx — because its run also needs the artifact's
// server-persisted quiz_state, not just the questions.)
export function StudyViewer({ artifactId }: { artifactId: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["artifact-file", artifactId],
    queryFn: ({ signal }) => readArtifactFile<FlashcardDeck>(artifactId, signal),
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
      <p className={`${VIEWER_PADDING} text-sm text-destructive`}>
        {error instanceof Error
          ? error.message
          : "Failed to load this artifact"}
      </p>
    )
  }
  return <FlashcardsViewer deck={data} />
}
