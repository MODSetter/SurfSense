export const RIGHT_PANEL_KEY = "surfsense:right-panel:v1"

export function readRightPanelOpen() {
  try {
    return localStorage.getItem(RIGHT_PANEL_KEY) !== "collapsed"
  } catch {
    return true
  }
}

export function writeRightPanelOpen(open: boolean) {
  try {
    localStorage.setItem(RIGHT_PANEL_KEY, open ? "open" : "collapsed")
  } catch {
    // Private browsing and full disks throw.
  }
}
