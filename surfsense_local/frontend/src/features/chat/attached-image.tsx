import { useEffect, useState } from "react"
import { AttachmentPrimitive, useAuiState } from "@assistant-ui/react"

import { XIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

/** Where the current attachment's picture can be drawn from. */
function useAttachmentSource(): string | null {
  const file = useAuiState(({ attachment }) => attachment.file ?? null)
  const stored = useAuiState(({ attachment }) => {
    const part = attachment.content?.find((p) => p.type === "image")
    return part?.type === "image" ? part.image : null
  })
  const [preview, setPreview] = useState<{ file: File; url: string } | null>(
    null
  )

  // A pending attachment is only a File until it is sent. Read as a data URL
  // rather than an object URL: nothing to revoke, so StrictMode's double
  // effect cannot free a picture that is still on screen.
  useEffect(() => {
    if (!file) return
    let current = true
    const reader = new FileReader()
    reader.onload = () => {
      if (current && typeof reader.result === "string") {
        setPreview({ file, url: reader.result })
      }
    }
    reader.readAsDataURL(file)
    return () => {
      current = false
    }
  }, [file])

  return stored ?? (file && preview?.file === file ? preview.url : null)
}

function Thumbnail({ className }: { className: string }) {
  const source = useAttachmentSource()
  const alt = intl.formatMessage({
    id: "chat_attached_image_aria",
    defaultMessage: "Attached image",
  })
  return source ? (
    <img src={source} alt={alt} className={className} />
  ) : (
    <div aria-label={alt} className={cn(className, "bg-muted")} />
  )
}

/** A picked image in the composer, with its remove control. */
export function ComposerImage() {
  return (
    <AttachmentPrimitive.Root className="group relative size-14 shrink-0">
      <Thumbnail className="size-14 rounded-lg border object-cover" />
      <AttachmentPrimitive.Remove
        aria-label={intl.formatMessage({
          id: "chat_attached_image_remove_aria",
          defaultMessage: "Remove image",
        })}
        className="absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full border bg-background text-muted-foreground shadow-sm transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <XIcon className="size-3" />
      </AttachmentPrimitive.Remove>
    </AttachmentPrimitive.Root>
  )
}

/** An image a sent turn carried, above its bubble. */
export function MessageImage() {
  return (
    <AttachmentPrimitive.Root>
      <Thumbnail className="max-h-48 max-w-48 rounded-xl border object-cover" />
    </AttachmentPrimitive.Root>
  )
}
