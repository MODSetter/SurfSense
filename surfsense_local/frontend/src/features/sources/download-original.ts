import { IN_CONTAINER } from "@/app/in-container"

import { originalDocumentUrl } from "./api"

/**
 * The Docker build: an upload's file lives in the container, where no app on
 * the user's computer can open it or show its folder, so the browser downloads
 * it instead (docs/architecture/docker.md, The frontend without Electron).
 */
export function downloadsOriginals(): boolean {
  return IN_CONTAINER
}

/** The API answers with the file as an attachment, never inline. */
export function downloadOriginal(
  workspaceId: number,
  documentId: number
): void {
  const link = document.createElement("a")
  link.href = originalDocumentUrl(workspaceId, documentId)
  link.download = ""
  document.body.append(link)
  link.click()
  link.remove()
}
