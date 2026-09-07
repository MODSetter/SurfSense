import { useEffect, useRef, useState } from "react"

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)"

function useTypewriter(text: string, placeholder = "New chat", speed = 35) {
  const [displayed, setDisplayed] = useState(text)
  const previous = useRef(text)

  useEffect(() => {
    const prior = previous.current
    previous.current = text
    if (
      prior !== placeholder ||
      text === placeholder ||
      !text ||
      window.matchMedia?.(REDUCED_MOTION_QUERY).matches
    ) {
      setDisplayed(text)
      return
    }

    setDisplayed("")
    let length = 0
    const interval = window.setInterval(() => {
      length += 1
      setDisplayed(text.slice(0, length))
      if (length >= text.length) {
        window.clearInterval(interval)
      }
    }, speed)
    return () => window.clearInterval(interval)
  }, [placeholder, speed, text])

  return displayed
}

export function TypewriterText({ text }: { text: string }) {
  const displayed = useTypewriter(text)
  return (
    <>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true">{displayed}</span>
    </>
  )
}
