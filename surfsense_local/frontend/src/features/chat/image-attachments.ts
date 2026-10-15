import {
  SimpleImageAttachmentAdapter,
  type AppendMessage,
  type CreateAttachment,
  type ThreadMessageLike,
} from "@assistant-ui/react"

import { apiUrl } from "@/lib/api"

import type { ChatMessage, ImageUpload } from "./api"

// The formats the backend normalises (modules/chat/images/intake.py). Wider
// than this and the picker offers HEIC or SVG only for the send to refuse them.
export const IMAGE_ACCEPT =
  "image/png,image/jpeg,image/webp,image/gif,image/bmp,image/tiff"

/** assistant-ui's own image adapter, narrowed to what the backend accepts. */
export class ChatImageAdapter extends SimpleImageAttachmentAdapter {
  override accept = IMAGE_ACCEPT
}

type MessageAttachment = NonNullable<ThreadMessageLike["attachments"]>[number]

/** The images a composed message carries, as the request sends them. */
export function uploadsOf(message: AppendMessage): ImageUpload[] {
  return (message.attachments ?? []).flatMap((attachment) =>
    (attachment.content ?? []).flatMap((part) =>
      part.type === "image" ? [toUpload(part.image)] : []
    )
  )
}

function toUpload(dataUrl: string): ImageUpload {
  const [header, data = ""] = dataUrl.split(",", 2)
  const mime = /^data:([^;]+);base64$/.exec(header ?? "")?.[1] ?? null
  return { mime, data }
}

/** A stored or just-sent turn's images as attachments the thread can draw. */
export function attachmentsOf(
  message: ChatMessage,
  threadId: number | null
): MessageAttachment[] {
  const stored = (message.content.images ?? []).map((_, index) =>
    typeof message.id === "number" && threadId !== null
      ? apiUrl(
          `/chat/threads/${threadId}/messages/${message.id}/images/${index}`
        )
      : null
  )
  // Before the turn is stored, the picture the person picked stands in.
  const sources = stored.some((url) => url !== null)
    ? stored
    : (message.content.previews ?? [])
  return sources.flatMap((url, index) =>
    url
      ? [
          {
            id: `${message.id}-image-${index}`,
            type: "image",
            name: `image-${index + 1}`,
            status: { type: "complete" },
            content: [{ type: "image", image: url }],
          },
        ]
      : []
  )
}

/** A data URL for a previewed upload, which is what the thread shows first. */
export function previewOf(upload: ImageUpload): string {
  return `data:${upload.mime ?? "image/png"};base64,${upload.data}`
}

/** An image a refused send hands back, attached to the composer again as it was. */
export function composerAttachmentOf(
  upload: ImageUpload,
  index: number
): CreateAttachment {
  return {
    type: "image",
    name: `image-${index + 1}`,
    contentType: upload.mime ?? "image/png",
    content: [{ type: "image", image: previewOf(upload) }],
  }
}
