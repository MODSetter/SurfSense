export type MotionPreference = "system" | "on" | "off"

// index.html reads these before the bundle loads, so the first frame is right;
// its test fails if the two disagree.
export const MOTION_PREFERENCE_KEY = "surfsense:reduce-motion:v1"
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)"
const ROOT_CLASS = "reduce-motion"

export function readMotionPreference(): MotionPreference {
  try {
    const saved = localStorage.getItem(MOTION_PREFERENCE_KEY)
    return saved === "on" || saved === "off" ? saved : "system"
  } catch {
    return "system"
  }
}

function systemAsksToReduce(): boolean {
  return window.matchMedia?.(REDUCED_MOTION_QUERY).matches ?? false
}

/** For code that animates from script; CSS reads the root class instead. */
export function motionIsReduced(): boolean {
  const preference = readMotionPreference()
  return preference === "system" ? systemAsksToReduce() : preference === "on"
}

function applyToRoot(): void {
  document.documentElement.classList.toggle(ROOT_CLASS, motionIsReduced())
}

export function setMotionPreference(preference: MotionPreference): void {
  try {
    localStorage.setItem(MOTION_PREFERENCE_KEY, preference)
  } catch {
    // Without storage, the choice cannot be kept.
  }
  applyToRoot()
}

/** Keeps the root class right when the OS setting or another tab's choice changes. */
export function followMotionPreference(): void {
  applyToRoot()
  window
    .matchMedia?.(REDUCED_MOTION_QUERY)
    .addEventListener?.("change", applyToRoot)
  window.addEventListener("storage", (event) => {
    if (event.key === MOTION_PREFERENCE_KEY || event.key === null) applyToRoot()
  })
}
