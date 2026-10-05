import { request } from "@/lib/api"

import type { ChatMessage, ImageUpload } from "../api"

/** A stored question's images, read back to send again with a retry. */
export async function storedUploads(
  threadId: number,
  question: ChatMessage
): Promise<ImageUpload[]> {
  const images = question.content.images ?? []
  return Promise.all(
    images.map(async (image, index) => {
      const response = await request(
        `/chat/threads/${threadId}/messages/${question.id}/images/${index}`
      )
      return { mime: image.mime, data: await base64(await response.blob()) }
    })
  )
}

function base64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "")
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}
