import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { CheckIcon, CopyIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

// Long enough to read "Copied", short enough that a second copy is not blocked.
const COPIED_MS = 2000

export function CopySystemInfoButton({ text }: { text: string }) {
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

  return (
    <Button type="button" variant="outline" onClick={() => void copy()}>
      {copied ? (
        <CheckIcon data-icon="inline-start" />
      ) : (
        <CopyIcon data-icon="inline-start" />
      )}
      {copied
        ? intl.formatMessage({
            id: "about_system_info_copied_button",
            defaultMessage: "Copied",
          })
        : intl.formatMessage({
            id: "about_system_info_copy_button",
            defaultMessage: "Copy system info",
          })}
    </Button>
  )
}
