import type { RightTab } from "./right-panel"

export const RIGHT_RAIL_KEY = "surfsense:right-rail:v1"
export const RIGHT_TAB_KEY = "surfsense:right-tab:v1"

export function readRightRailOpen() {
  try {
    return localStorage.getItem(RIGHT_RAIL_KEY) !== "collapsed"
  } catch {
    return true
  }
}

export function writeRightRailOpen(open: boolean) {
  try {
    localStorage.setItem(RIGHT_RAIL_KEY, open ? "open" : "collapsed")
  } catch {
    // Private browsing and full disks throw.
  }
}

export function readRightTab(): RightTab {
  try {
    return localStorage.getItem(RIGHT_TAB_KEY) === "artifacts"
      ? "artifacts"
      : "sources"
  } catch {
    return "sources"
  }
}

export function writeRightTab(tab: RightTab) {
  try {
    localStorage.setItem(RIGHT_TAB_KEY, tab)
  } catch {
    // Private browsing and full disks throw.
  }
}
