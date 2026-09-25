import { useEffect, useState } from "react"

// Long enough to read the confirmation, short enough that a second copy is not blocked.
const COPIED_MS = 2000

export function useCopyToClipboard(text: string) {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopied(false), COPIED_MS)
    return () => window.clearTimeout(timer)
  }, [copied])

  const copy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
  }

  return { copied, copy }
}
