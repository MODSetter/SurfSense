import type { ModelSelection } from "@/features/models/selection/api"

export const THINKING_KEY = "surfsense:chat-thinking:v1"

/** Only the local runtime has a way to be told not to think. */
export function canSkipThinking(model: ModelSelection | null | undefined) {
  return model?.provider === "llamacpp"
}

export function readThinkingOn() {
  try {
    return localStorage.getItem(THINKING_KEY) !== "off"
  } catch {
    return true
  }
}

export function writeThinkingOn(on: boolean) {
  try {
    localStorage.setItem(THINKING_KEY, on ? "on" : "off")
  } catch {
    // Private browsing and full disks throw.
  }
}
