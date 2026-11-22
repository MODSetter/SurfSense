import { BrowserWindow } from "electron"

import { captureHeight, CAPTURE_WIDTH } from "./capture-size.ts"

// Scripts draw charts and figures after load; this is long enough for a calm
// page to settle, and the page shows its end state under reduced motion anyway.
const SETTLE_MS = 1000
// Resizing to the page's height lays it out again before the capture.
const RESIZE_MS = 300

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Capture a model-written web page as the agent's screenshots: loaded as the
 * API serves it, at the viewer's width, with reduced motion on so animations
 * show their end state, as tall as the page up to four screens.
 */
export async function captureWebPage(
  session: Electron.Session,
  fileUrl: string,
  signal: AbortSignal,
): Promise<Uint8Array> {
  const win = new BrowserWindow({
    show: false,
    width: CAPTURE_WIDTH,
    height: 1000,
    useContentSize: true,
    // A long page is captured taller than the screen.
    enableLargerThanScreen: true,
    webPreferences: {
      session,
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  })
  const stay = (event: Electron.Event) => event.preventDefault()
  win.webContents.on("will-navigate", stay)
  win.webContents.on("will-frame-navigate", stay)
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }))
  const close = () => win.destroy()
  signal.addEventListener("abort", close, { once: true })
  try {
    // Emulation set before the window has a page never answers (measured on
    // Electron 44), so the page loads after a blank one, already in reduced motion.
    await win.loadURL("about:blank")
    win.webContents.debugger.attach("1.3")
    await win.webContents.debugger.sendCommand("Emulation.setEmulatedMedia", {
      features: [{ name: "prefers-reduced-motion", value: "reduce" }],
    })
    await win.loadURL(fileUrl)
    await wait(SETTLE_MS)
    const scrolled: unknown = await win.webContents.executeJavaScript(
      "document.documentElement.scrollHeight",
    )
    win.setContentSize(CAPTURE_WIDTH, captureHeight(scrolled))
    await wait(RESIZE_MS)
    const image = await win.webContents.capturePage()
    // A 2x display captures twice as wide; the API cuts screens from 1,280 px.
    return image.resize({ width: CAPTURE_WIDTH, quality: "best" }).toPNG()
  } finally {
    signal.removeEventListener("abort", close)
    if (!win.isDestroyed()) win.destroy()
  }
}
