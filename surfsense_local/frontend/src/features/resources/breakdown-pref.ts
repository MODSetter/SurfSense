const BREAKDOWN_KEY = "surfsense:resources-breakdown:v1"

export function readBreakdownOpen(): boolean {
  try {
    return localStorage.getItem(BREAKDOWN_KEY) === "open"
  } catch {
    return false
  }
}

export function writeBreakdownOpen(open: boolean): void {
  try {
    localStorage.setItem(BREAKDOWN_KEY, open ? "open" : "closed")
  } catch {
    // Private browsing and full disks throw.
  }
}
