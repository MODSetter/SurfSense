import { readFileSync, renameSync, writeFileSync } from "node:fs"
import { join } from "node:path"

import { app, type BrowserWindow, type Rectangle, screen } from "electron"

export type WindowState = {
  bounds: Rectangle
  maximized: boolean
}

const MIN_WIDTH = 480
const MIN_HEIGHT = 320

function statePath(): string {
  return join(app.getPath("userData"), "window-state.json")
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value)
}

function parseState(value: unknown): WindowState | null {
  if (!value || typeof value !== "object") return null
  const state = value as Partial<WindowState>
  const bounds = state.bounds
  if (
    !bounds ||
    !isFiniteNumber(bounds.x) ||
    !isFiniteNumber(bounds.y) ||
    !isFiniteNumber(bounds.width) ||
    !isFiniteNumber(bounds.height) ||
    bounds.width <= 0 ||
    bounds.height <= 0 ||
    typeof state.maximized !== "boolean"
  ) {
    return null
  }
  return { bounds, maximized: state.maximized }
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum)
}

function visibleBounds(bounds: Rectangle): Rectangle {
  const workArea = screen.getDisplayMatching(bounds).workArea
  const width = Math.min(
    Math.max(Math.round(bounds.width), MIN_WIDTH),
    workArea.width,
  )
  const height = Math.min(
    Math.max(Math.round(bounds.height), MIN_HEIGHT),
    workArea.height,
  )
  return {
    x: clamp(
      Math.round(bounds.x),
      workArea.x,
      workArea.x + workArea.width - width,
    ),
    y: clamp(
      Math.round(bounds.y),
      workArea.y,
      workArea.y + workArea.height - height,
    ),
    width,
    height,
  }
}

export function loadWindowState(): WindowState | null {
  try {
    const state = parseState(JSON.parse(readFileSync(statePath(), "utf8")))
    return state ? { ...state, bounds: visibleBounds(state.bounds) } : null
  } catch {
    return null
  }
}

export function saveWindowState(win: BrowserWindow): void {
  try {
    const path = statePath()
    const temporary = `${path}.tmp`
    const state: WindowState = {
      bounds: win.getNormalBounds(),
      maximized: win.isMaximized(),
    }
    writeFileSync(temporary, JSON.stringify(state))
    renameSync(temporary, path)
  } catch (error) {
    // ponytail: window state is best-effort; failing to save must never block exit.
    process.stderr.write(
      `[main] failed to save window state: ${String(error)}\n`,
    )
  }
}
