// Holds the identity of the database whose onboarding was last seen done.
const DASHBOARD_HINT_KEY = "surfsense:startup-dashboard:v1"

// Docker has no bridge, so it never expects the dashboard: its data volume can
// be replaced under a browser that still remembers the old one.
function databaseIdentity(): string | null {
  try {
    return window.surfsense?.databaseIdentity?.() ?? null
  } catch {
    return null
  }
}

/**
 * Whether startup will open the dashboard, guessed before the API answers so
 * the loading screen can draw it. Only a hint: wrong, it costs one frame, and
 * on a database made since it was remembered it never guesses yes.
 */
export function expectsDashboard(): boolean {
  const identity = databaseIdentity()
  if (identity === null) return false
  try {
    return localStorage.getItem(DASHBOARD_HINT_KEY) === identity
  } catch {
    return false
  }
}

export function rememberDashboard(): void {
  const identity = databaseIdentity()
  if (identity === null) return
  try {
    localStorage.setItem(DASHBOARD_HINT_KEY, identity)
  } catch {
    // Without storage, every launch shows the plain loading screen.
  }
}

export function forgetDashboard(): void {
  try {
    localStorage.removeItem(DASHBOARD_HINT_KEY)
  } catch {
    // Nothing was stored.
  }
}
