import type { ModelSelection } from "@/features/models/selection/api"

export const THINKING_KEY = "surfsense:chat-thinking:v1"

/** Only the local runtime has a way to be told not to think. */
export function canSkipThinking(model: ModelSelection | null | undefined) {
  return model?.provider === "llamacpp"
}

// The choice a failed write could not store, so the switch and the next
// request still agree for as long as the window lives.
let unsaved: boolean | null = null

export function readThinkingOn() {
  if (unsaved !== null) return unsaved
  try {
    return localStorage.getItem(THINKING_KEY) !== "off"
  } catch {
    return true
  }
}

export function writeThinkingOn(on: boolean) {
  try {
    localStorage.setItem(THINKING_KEY, on ? "on" : "off")
    unsaved = null
  } catch {
    // Private browsing and full disks throw.
    unsaved = on
  }
}
