import { join } from "node:path"

/** What a move of the models folder carries; nothing else in the data folder goes with it. */
export const MODEL_FOLDER_NAMES = ["models", "audio", "images", "embeddings"] as const

export function modelFolders(root: string): {
  generation: string
  audio: string
  images: string
  embeddings: string
} {
  return {
    generation: join(root, "models"),
    audio: join(root, "audio"),
    images: join(root, "images"),
    embeddings: join(root, "embeddings"),
  }
}
