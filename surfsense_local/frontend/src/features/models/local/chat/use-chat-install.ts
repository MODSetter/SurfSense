import { createInstall } from "../create-install"

export type { InstallState } from "../create-install"

/**
 * One install at a time. Curated and searched builds go through the same
 * call, because the id is opaque either way. The server selects what it
 * installs, so a finished install is also a new chat model.
 */
export const useChatInstall = createInstall({ select: true })
