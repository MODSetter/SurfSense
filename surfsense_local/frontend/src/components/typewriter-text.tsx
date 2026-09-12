import { useEffect, useState } from "react"

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)"

function AnimatedText({
  text,
  onComplete,
  speed = 35,
}: {
  text: string
  onComplete?: () => void
  speed?: number
}) {
  const [length, setLength] = useState(0)
  useEffect(() => {
    let next = 0
    const interval = window.setInterval(() => {
      next += 1
      setLength(next)
      if (next >= text.length) {
        window.clearInterval(interval)
        onComplete?.()
      }
    }, speed)
    return () => window.clearInterval(interval)
  }, [onComplete, speed, text])

  return <span aria-hidden="true">{text.slice(0, length)}</span>
}

function CompleteAnimation({ onComplete }: { onComplete?: () => void }) {
  useEffect(() => {
    onComplete?.()
  }, [onComplete])
  return null
}

export function TypewriterText({
  text,
  animate = false,
  onComplete,
}: {
  text: string
  animate?: boolean
  onComplete?: () => void
}) {
  const reducedMotion =
    window.matchMedia?.(REDUCED_MOTION_QUERY).matches ?? false
  return (
    <>
      <span className="sr-only">{text}</span>
      {animate && !reducedMotion ? (
        <AnimatedText text={text} onComplete={onComplete} />
      ) : (
        <span aria-hidden="true">{text}</span>
      )}
      {animate && reducedMotion ? (
        <CompleteAnimation onComplete={onComplete} />
      ) : null}
    </>
  )
}
