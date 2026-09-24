import { createInstall } from "../create-install"

/** Downloading does not select: an image model is picked once it is on disk. */
export const useImageInstall = createInstall({ select: false })
