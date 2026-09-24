import { createInstall } from "../create-install"

/** Downloading does not select: an audio model is picked once it is on disk. */
export const useAudioInstall = createInstall({ select: false })
