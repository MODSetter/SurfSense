import katex from "katex"
import "katex/dist/katex.min.css"
import { useLayoutEffect, useMemo, useRef } from "react"

import { cn } from "@/lib/utils"
import { parseStudyText } from "./parse-study-text"

const KATEX_OPTIONS = {
  output: "htmlAndMathml",
  throwOnError: false,
  trust: false,
  strict: "error",
  maxExpand: 1_000,
  maxSize: 10,
} as const

function Formula({ value, display }: { value: string; display: boolean }) {
  const containerRef = useRef<HTMLSpanElement>(null)

  useLayoutEffect(() => {
    if (containerRef.current) {
      katex.render(value, containerRef.current, {
        ...KATEX_OPTIONS,
        displayMode: display,
      })
    }
  }, [display, value])

  return (
    <span
      ref={containerRef}
      className={
        display
          ? "my-2 block max-w-full overflow-x-auto overflow-y-hidden py-1"
          : "inline-block max-w-full align-middle"
      }
    />
  )
}

// Renders quiz/flashcards content — plain text with optional \(...\)/\[...\]
// LaTeX (see the format prompt in worker/studio/content/quiz/pipeline.py).
// Unlike surfsense_web's version, this never throws on malformed LaTeX: that
// codebase validates the delimiter contract server-side before an artifact
// is ever saved (verify_artifact + QuizSchema), so a parse failure there
// means a broken invariant worth crashing on. This backend has no such
// upstream check, so a parse failure here just means "render it as text."
export function StudyText({
  content,
  className,
}: {
  content: string
  className?: string
}) {
  const segments = useMemo(() => parseStudyText(content), [content])

  if (!segments) {
    return (
      <span className={cn("whitespace-pre-wrap", className)}>{content}</span>
    )
  }

  return (
    <span className={cn("whitespace-pre-wrap", className)}>
      {segments.map((segment) =>
        segment.type === "text" ? (
          <span key={segment.offset}>{segment.value}</span>
        ) : (
          <Formula
            key={segment.offset}
            value={segment.value}
            display={segment.display}
          />
        )
      )}
    </span>
  )
}
