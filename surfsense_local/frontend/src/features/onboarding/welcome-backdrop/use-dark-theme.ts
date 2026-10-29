import { useSyncExternalStore } from "react"

// The theme provider resolves "system" itself and only exposes the setting,
// so the applied `.dark` class is the one place that says what is showing.
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange)
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  })
  return () => observer.disconnect()
}

function isDark() {
  return document.documentElement.classList.contains("dark")
}

export function useDarkTheme() {
  return useSyncExternalStore(subscribe, isDark)
}
