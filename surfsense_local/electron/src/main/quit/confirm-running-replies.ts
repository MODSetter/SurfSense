export type QuitConfirmation = {
  // How many replies the API is writing right now.
  countRunning: () => Promise<number>
  // Whether the person still wants to quit, told how many would be cut off.
  ask: (count: number) => Promise<boolean>
  // The API stores every reply's text so far before the sidecars stop.
  saveRunning: () => Promise<void>
}

/**
 * Whether to go ahead with a quit. Asks only while replies are being written,
 * and saves them before saying yes. Neither an API that cannot be reached nor
 * a save that fails holds the quit: the next start marks what was cut off.
 */
export async function confirmQuit({
  countRunning,
  ask,
  saveRunning,
}: QuitConfirmation): Promise<boolean> {
  const running = await countRunning().catch(() => 0)
  if (running === 0) return true
  if (!(await ask(running))) return false
  await saveRunning().catch(() => undefined)
  return true
}
