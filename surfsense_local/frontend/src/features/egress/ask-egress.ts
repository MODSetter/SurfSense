/**
 * The handle a mounted prompt leaves for callers that have no refused request
 * to speak for them. It mirrors `setEgressPrompt` in `lib/api`, from the other
 * direction: the API layer routes refusals to the dialog, and this routes
 * questions asked before any call is made.
 */

export type Pending = {
  destination: string
  host: string
  // What Allow does. A refused request enables the destination and is retried;
  // the updater talks to GitHub from Electron, so its consent is a pref there.
  allow: () => Promise<unknown>
  resolve: (allowed: boolean) => void
}

export type AskHandler = (request: Omit<Pending, "resolve">) => Promise<boolean>

// Set while the dialog is mounted, for callers the API layer cannot speak for.
let ask: AskHandler | null = null

export function setAskHandler(handler: AskHandler | null): void {
  ask = handler
}

/**
 * Ask outside a refused request: either because none can raise the question,
 * the call not being the backend's to make, or because the answer is wanted
 * before the request rather than after it, where a refusal would otherwise be
 * the user's first news that a feature is off.
 *
 * Resolves false when the prompt is not mounted, so a caller outside the app
 * shell simply gets no consent rather than an error.
 */
export function askEgress(request: Omit<Pending, "resolve">): Promise<boolean> {
  return ask ? ask(request) : Promise.resolve(false)
}
