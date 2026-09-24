import { createInstall } from "../create-install"

export type { InstallState } from "../create-install"

/**
 * One install at a time. Curated and searched builds go through the same
 * call, because the id is opaque either way. Downloading does not select: a
 * model is chosen with Use once it is on disk, same as an image model.
 * Onboarding's model step picks its own `select: true` install instead, since
 * choosing a first model there should need no second click.
 */
export const useChatInstall = createInstall({ select: false })
