import { BrowserWindow, screen, shell } from 'electron';
import path from 'path';
import { getServerPort } from '../server';

const TOOLTIP_WIDTH = 420;
const TOOLTIP_HEIGHT = 38;
const MAX_HEIGHT = 400;

let suggestionWindow: BrowserWindow | null = null;
let resizeTimer: ReturnType<typeof setInterval> | null = null;
let cursorOrigin = { x: 0, y: 0 };

const CURSOR_GAP = 20;

function positionOnScreen(cursorX: number, cursorY: number, w: number, h: number): { x: number; y: number } {
  const display = screen.getDisplayNearestPoint({ x: cursorX, y: cursorY });
  const { x: dx, y: dy, width: dw, height: dh } = display.workArea;

  const x = Math.max(dx, Math.min(cursorX, dx + dw - w));

  const spaceBelow = (dy + dh) - (cursorY + CURSOR_GAP);
  const y = spaceBelow >= h
    ? cursorY + CURSOR_GAP
    : cursorY - h - CURSOR_GAP;

  return { x, y: Math.max(dy, y) };
}

function stopResizePolling(): void {
  if (resizeTimer) { clearInterval(resizeTimer); resizeTimer = null; }
}

function startResizePolling(win: BrowserWindow): void {
  stopResizePolling();
  let lastH = 0;
  resizeTimer = setInterval(async () => {
    if (!win || win.isDestroyed()) { stopResizePolling(); return; }
    try {
      const h: number = await win.webContents.executeJavaScript(
        `document.body.scrollHeight`
      );
      if (h > 0 && h !== lastH) {
        lastH = h;
        const clamped = Math.min(h, MAX_HEIGHT);
        const pos = positionOnScreen(cursorOrigin.x, cursorOrigin.y, TOOLTIP_WIDTH, clamped);
        win.setBounds({ x: pos.x, y: pos.y, width: TOOLTIP_WIDTH, height: clamped });
      }
    } catch {}
  }, 150);
}

export function getSuggestionWindow(): BrowserWindow | null {
  return suggestionWindow;
}

export function destroySuggestion(): void {
  stopResizePolling();
  if (suggestionWindow && !suggestionWindow.isDestroyed()) {
    suggestionWindow.close();
  }
  suggestionWindow = null;
}

export function createSuggestionWindow(x: number, y: number): BrowserWindow {
  destroySuggestion();
  cursorOrigin = { x, y };

  const pos = positionOnScreen(x, y, TOOLTIP_WIDTH, TOOLTIP_HEIGHT);

  suggestionWindow = new BrowserWindow({
    width: TOOLTIP_WIDTH,
    height: TOOLTIP_HEIGHT,
    x: pos.x,
    y: pos.y,
    frame: false,
    transparent: true,
    focusable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: true,
    type: 'panel',
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
    show: false,
  });

  suggestionWindow.loadURL(`http://localhost:${getServerPort()}/desktop/suggestion?t=${Date.now()}`);

  suggestionWindow.once('ready-to-show', () => {
    suggestionWindow?.showInactive();
    if (suggestionWindow) startResizePolling(suggestionWindow);
  });

  suggestionWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://localhost')) {
      return { action: 'allow' };
    }
    shell.openExternal(url);
    return { action: 'deny' };
  });

  suggestionWindow.on('closed', () => {
    stopResizePolling();
    suggestionWindow = null;
  });

  return suggestionWindow;
}
