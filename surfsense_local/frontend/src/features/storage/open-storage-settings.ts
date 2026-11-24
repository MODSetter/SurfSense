// A full-disk toast can fire anywhere, Settings only exists once the dashboard
// does: onboarding has no one listening, and its toast offers nothing to open.
let listener: (() => void) | null = null

export function onStorageSettingsRequested(next: () => void): () => void {
  listener = next
  return () => {
    if (listener === next) listener = null
  }
}

export function canOpenStorageSettings(): boolean {
  return listener !== null && window.surfsense?.storage !== undefined
}

export function openStorageSettings(): void {
  listener?.()
}
