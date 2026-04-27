import { BrowserWindow, desktopCapturer, ipcMain, screen } from 'electron';
import path from 'path';
import { IPC_CHANNELS } from '../ipc/channels';

let pickInProgress = false;

const PREVIEW_THUMB = { width: 280, height: 180 } as const;

function maxCaptureThumbSize(): { width: number; height: number } {
  const d = screen.getPrimaryDisplay();
  const sf = d.scaleFactor || 1;
  const w = Math.min(3840, Math.max(1280, Math.round(d.size.width * sf)));
  const h = Math.min(2160, Math.max(720, Math.round(d.size.height * sf)));
  return { width: w, height: h };
}

function isDesktopWindowSourceId(s: string): boolean {
  return typeof s === 'string' && s.startsWith('window:');
}

export type PickedWindowResult = {
  sourceId: string;
  /** Same pixels as the one `desktopCapturer` snapshot (max thumbnail size). */
  dataUrl: string;
};

function buildPickerInjectScript(): string {
  return `(async function () {
    const api = window.surfsenseWindowPick;
    if (!api) return;
    const items = await api.list();
    document.body.style.cssText =
      'margin:0;font-family:system-ui,-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding:16px;box-sizing:border-box;';
    const top = document.createElement('div');
    top.style.cssText =
      'display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px;';
    const t = document.createElement('strong');
    t.textContent = 'Open windows';
    const hint = document.createElement('span');
    hint.style.cssText = 'opacity:0.75;font-size:13px;';
    hint.textContent = 'Click a window · Esc to cancel';
    top.appendChild(t);
    top.appendChild(hint);
    document.body.appendChild(top);
    if (!items || !items.length) {
      const p = document.createElement('p');
      p.style.cssText = 'line-height:1.5;max-width:42rem;';
      p.textContent =
        'No windows were returned by the system. On Linux, allow screen capture when prompted. If other apps are open, try again.';
      document.body.appendChild(p);
      return;
    }
    const grid = document.createElement('div');
    grid.style.cssText =
      'display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;max-height:calc(100vh - 88px);overflow:auto;padding-bottom:8px;';
    for (const it of items) {
      const card = document.createElement('button');
      card.type = 'button';
      card.style.cssText =
        'text-align:left;background:#1e293b;border:1px solid #334155;border-radius:8px;padding:8px;cursor:pointer;color:inherit;';
      card.addEventListener('mouseenter', function () {
        card.style.borderColor = '#38bdf8';
      });
      card.addEventListener('mouseleave', function () {
        card.style.borderColor = '#334155';
      });
      const img = document.createElement('img');
      img.alt = '';
      img.src =
        it.thumbDataUrl ||
        'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';
      img.style.cssText =
        'width:100%;height:100px;object-fit:cover;border-radius:4px;background:#000;display:block;';
      const cap = document.createElement('div');
      cap.textContent = it.name || '(untitled)';
      cap.style.cssText =
        'margin-top:6px;font-size:12px;line-height:1.35;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;';
      card.appendChild(img);
      card.appendChild(cap);
      card.addEventListener('click', function () {
        api.submit(it.id);
      });
      grid.appendChild(card);
    }
    document.body.appendChild(grid);
    window.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') api.cancel();
    });
  })();`;
}

/**
 * One OS / Chromium capture session: `getSources` runs once (important on Wayland /
 * PipeWire so the portal is not opened again for the same flow). Opens our grid to
 * choose a window; resolves with the chosen snapshot for region or full-frame use.
 */
export function pickOpenWindowCapture(): Promise<PickedWindowResult | null> {
  if (pickInProgress) return Promise.resolve(null);
  pickInProgress = true;

  return new Promise((resolve) => {
    let settled = false;
    let picker: BrowserWindow | null = null;
    let pickerWc: Electron.WebContents | null = null;
    /** Filled once before the grid runs — reused for list + final image (no second getSources). */
    let sessionSources: Electron.DesktopCapturerSource[] = [];

    const finish = (result: PickedWindowResult | null) => {
      if (settled) return;
      settled = true;
      pickInProgress = false;
      ipcMain.removeHandler(IPC_CHANNELS.WINDOW_PICK_LIST);
      const wc = pickerWc;
      pickerWc = null;
      if (wc && !wc.isDestroyed()) {
        wc.removeListener('before-input-event', onBeforeInput);
        wc.ipc.removeListener(IPC_CHANNELS.WINDOW_PICK_SUBMIT, onSubmit);
        wc.ipc.removeListener(IPC_CHANNELS.WINDOW_PICK_CANCEL, onCancel);
      }
      if (picker && !picker.isDestroyed()) {
        picker.removeAllListeners('closed');
        picker.close();
      }
      picker = null;
      resolve(result);
    };

    const onSubmit = (_event: Electron.IpcMainEvent, sourceId: string) => {
      if (settled || !picker || picker.isDestroyed()) return;
      if (!isDesktopWindowSourceId(sourceId)) {
        finish(null);
        return;
      }
      const hit = sessionSources.find((s) => s.id === sourceId);
      if (!hit || hit.thumbnail.isEmpty()) {
        finish(null);
        return;
      }
      finish({ sourceId, dataUrl: hit.thumbnail.toDataURL() });
    };

    const onCancel = () => {
      if (settled || !picker || picker.isDestroyed()) return;
      finish(null);
    };

    const onBeforeInput = (_event: Electron.Event, input: Electron.Input) => {
      if (input.type === 'keyDown' && input.key === 'Escape') {
        finish(null);
      }
    };

    ipcMain.handle(IPC_CHANNELS.WINDOW_PICK_LIST, async () => {
      return sessionSources.map((s, i) => {
        let thumbDataUrl = '';
        if (!s.thumbnail.isEmpty()) {
          try {
            const sm = s.thumbnail.resize({
              width: PREVIEW_THUMB.width,
              height: PREVIEW_THUMB.height,
              quality: 'good',
            });
            thumbDataUrl = sm.toDataURL();
          } catch {
            thumbDataUrl = s.thumbnail.toDataURL();
          }
        }
        return {
          id: s.id,
          name: (s.name || '').trim() || `Window ${i + 1}`,
          thumbDataUrl,
        };
      });
    });

    picker = new BrowserWindow({
      width: 760,
      height: 560,
      show: false,
      center: true,
      autoHideMenuBar: true,
      title: 'SurfSense — choose window',
      webPreferences: {
        preload: path.join(__dirname, 'window-picker-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
      },
    });

    pickerWc = picker.webContents;

    pickerWc.on('before-input-event', onBeforeInput);
    pickerWc.ipc.on(IPC_CHANNELS.WINDOW_PICK_SUBMIT, onSubmit);
    pickerWc.ipc.on(IPC_CHANNELS.WINDOW_PICK_CANCEL, onCancel);

    picker.on('closed', () => {
      if (!settled) finish(null);
    });

    picker
      .loadURL(
        'data:text/html;charset=utf-8,' +
          encodeURIComponent('<!doctype html><html><head><meta charset="utf-8"/></head><body></body></html>')
      )
      .catch(() => finish(null));

    picker.webContents.once('did-finish-load', () => {
      void (async () => {
        if (!picker || picker.isDestroyed()) return;
        let selfId = '';
        try {
          selfId = picker.getMediaSourceId();
        } catch {
          selfId = '';
        }
        try {
          const { width, height } = maxCaptureThumbSize();
          const sources = await desktopCapturer.getSources({
            types: ['window'],
            thumbnailSize: { width, height },
            fetchWindowIcons: false,
          });
          sessionSources = sources.filter((s) => !(selfId && s.id === selfId));
        } catch {
          sessionSources = [];
        }
        if (sessionSources.length === 1) {
          const only = sessionSources[0];
          if (!only.thumbnail.isEmpty()) {
            finish({ sourceId: only.id, dataUrl: only.thumbnail.toDataURL() });
            return;
          }
        }
        try {
          await picker.webContents.executeJavaScript(buildPickerInjectScript(), true);
          if (!picker.isDestroyed()) picker.show();
        } catch {
          finish(null);
        }
      })();
    });
  });
}
