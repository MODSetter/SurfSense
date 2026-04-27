import { BrowserWindow, desktopCapturer, nativeImage, screen } from 'electron';
import path from 'path';
import { IPC_CHANNELS } from '../ipc/channels';
function fitNativeImageToWorkArea(img: Electron.NativeImage, display: Electron.Display): Electron.NativeImage {
  const wa = display.workArea;
  const { width: iw, height: ih } = img.getSize();
  const scale = Math.min(1, wa.width / iw, wa.height / ih);
  if (scale >= 1) return img;
  return img.resize({
    width: Math.max(1, Math.floor(iw * scale)),
    height: Math.max(1, Math.floor(ih * scale)),
    quality: 'best',
  });
}

// One getSources per pick; overlay and final crop share that bitmap (avoids a second portal session, e.g. Wayland).

let pickInProgress = false;

type DisplayCaptureSnapshot = {
  dataUrl: string;
  width: number;
  height: number;
};

async function captureDisplaySnapshot(display: Electron.Display): Promise<DisplayCaptureSnapshot | null> {
  try {
    const sf = display.scaleFactor || 1;
    const tw = Math.max(1, Math.round(display.size.width * sf));
    const th = Math.max(1, Math.round(display.size.height * sf));
    const sources = await desktopCapturer.getSources({
      types: ['screen'],
      thumbnailSize: { width: tw, height: th },
    });
    if (!sources.length) return null;
    const idStr = String(display.id);
    let chosen =
      sources.find((s) => s.display_id === idStr) ||
      sources.find((s) => s.display_id && s.display_id === idStr) ||
      null;
    if (!chosen && screen.getPrimaryDisplay().id === display.id) {
      chosen = sources[0];
    }
    if (!chosen) chosen = sources[0];
    const dataUrl = chosen.thumbnail.toDataURL();
    const { width, height } = chosen.thumbnail.getSize();
    return { dataUrl, width, height };
  } catch {
    return null;
  }
}

export async function captureCurrentDisplayDataUrl(): Promise<string | null> {
  const display = screen.getDisplayNearestPoint(screen.getCursorScreenPoint());
  const snapshot = await captureDisplaySnapshot(display);
  return snapshot?.dataUrl ?? null;
}

function buildInjectScript(dataUrl: string, iw: number, ih: number): string {
  return `(() => {
    const api = window.surfsenseScreenRegion;
    if (!api) return;
    const dataUrl = ${JSON.stringify(dataUrl)};
    const iw = ${iw};
    const ih = ${ih};
    document.body.style.margin = '0';
    document.body.style.overflow = 'hidden';
    document.body.style.background = '#000';
    const img = document.createElement('img');
    img.draggable = false;
    img.src = dataUrl;
    img.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;object-fit:fill;user-select:none;pointer-events:none;';
    const veil = document.createElement('div');
    veil.style.cssText = 'position:fixed;inset:0;cursor:crosshair;background:rgba(0,0,0,0.15);';
    const sel = document.createElement('div');
    sel.style.cssText = 'position:fixed;border:2px solid #38bdf8;box-shadow:0 0 0 9999px rgba(0,0,0,0.45);display:none;pointer-events:none;z-index:2;';
    document.body.appendChild(img);
    document.body.appendChild(veil);
    document.body.appendChild(sel);
    let ax = 0, ay = 0, dragging = false;
    function show(x0, y0, x1, y1) {
      const l = Math.min(x0, x1), t = Math.min(y0, y1);
      const w = Math.abs(x1 - x0), h = Math.abs(y1 - y0);
      if (w < 2 || h < 2) { sel.style.display = 'none'; return; }
      sel.style.display = 'block';
      sel.style.left = l + 'px';
      sel.style.top = t + 'px';
      sel.style.width = w + 'px';
      sel.style.height = h + 'px';
    }
    function mapRect(l, t, w, h) {
      const vw = window.innerWidth, vh = window.innerHeight;
      const sx = Math.round((l / vw) * iw);
      const sy = Math.round((t / vh) * ih);
      const sw = Math.max(1, Math.round((w / vw) * iw));
      const sh = Math.max(1, Math.round((h / vh) * ih));
      const cx = Math.min(Math.max(0, sx), iw - 1);
      const cy = Math.min(Math.max(0, sy), ih - 1);
      const cw = Math.min(sw, iw - cx);
      const ch = Math.min(sh, ih - cy);
      return { x: cx, y: cy, width: cw, height: ch };
    }
    function endDrag(clientX, clientY, pointerId) {
      if (!dragging) return;
      dragging = false;
      if (typeof pointerId === 'number' && pointerId >= 0) {
        try { veil.releasePointerCapture(pointerId); } catch (_) {}
      }
      const l = Math.min(ax, clientX), t = Math.min(ay, clientY);
      const w = Math.abs(clientX - ax), h = Math.abs(clientY - ay);
      if (w < 4 || h < 4) { sel.style.display = 'none'; return; }
      api.submit(mapRect(l, t, w, h));
    }
    veil.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      try { veil.setPointerCapture(e.pointerId); } catch (_) {}
      dragging = true;
      ax = e.clientX; ay = e.clientY;
      show(ax, ay, ax, ay);
    });
    veil.addEventListener('pointermove', (e) => {
      if (!dragging) return;
      show(ax, ay, e.clientX, e.clientY);
    });
    veil.addEventListener('pointerup', (e) => {
      endDrag(e.clientX, e.clientY, e.pointerId);
    });
    window.addEventListener('pointerup', (e) => {
      endDrag(e.clientX, e.clientY, e.pointerId);
    });
    document.addEventListener(
      'mouseup',
      (e) => {
        endDrag(e.clientX, e.clientY, -1);
      },
      true
    );
    veil.addEventListener('pointercancel', (e) => {
      if (!dragging) return;
      dragging = false;
      try { veil.releasePointerCapture(e.pointerId); } catch (_) {}
      sel.style.display = 'none';
    });
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { api.cancel(); return; }
      if (e.key === 'Enter' && sel.style.display === 'block') {
        const l = parseFloat(sel.style.left), t = parseFloat(sel.style.top);
        const w = parseFloat(sel.style.width), h = parseFloat(sel.style.height);
        if (w >= 4 && h >= 4) api.submit(mapRect(l, t, w, h));
      }
    });
  })();`;
}

export function pickScreenRegion(opts?: { windowDataUrl?: string }): Promise<string | null> {
  if (pickInProgress) return Promise.resolve(null);
  pickInProgress = true;

  return new Promise((resolve) => {
    const display = screen.getDisplayNearestPoint(screen.getCursorScreenPoint());
    let settled = false;
    let overlay: BrowserWindow | null = null;
    /** webContents for listener removal after `BrowserWindow` may already be destroyed. */
    let overlayWc: Electron.WebContents | null = null;

    const cleanupListeners = () => {
      const wc = overlayWc;
      overlayWc = null;
      if (!wc || wc.isDestroyed()) return;
      wc.removeListener('before-input-event', onBeforeInput);
      wc.ipc.removeListener(IPC_CHANNELS.SCREEN_REGION_SUBMIT, onSubmit);
      wc.ipc.removeListener(IPC_CHANNELS.SCREEN_REGION_CANCEL, onCancel);
    };

    const finish = (result: string | null) => {
      if (settled) return;
      settled = true;
      pickInProgress = false;
      cleanupListeners();
      if (overlay && !overlay.isDestroyed()) {
        overlay.removeAllListeners('closed');
        overlay.close();
      }
      overlay = null;
      resolve(result);
    };

    let snapshot: DisplayCaptureSnapshot | null = null;
    let cropSource: Electron.NativeImage | null = null;

    const onSubmit = (
      _event: Electron.IpcMainEvent,
      rect: { x: number; y: number; width: number; height: number }
    ) => {
      if (settled || !overlay || overlay.isDestroyed()) return;
      if (!rect || rect.width < 1 || rect.height < 1) {
        finish(null);
        return;
      }
      if (!snapshot || !cropSource) {
        finish(null);
        return;
      }
      try {
        const iw = snapshot.width;
        const ih = snapshot.height;
        const { width: cw, height: ch } = cropSource.getSize();
        const scaleX = cw / iw;
        const scaleY = ch / ih;
        const ox = Math.floor(rect.x * scaleX);
        const oy = Math.floor(rect.y * scaleY);
        const ow = Math.min(Math.floor(rect.width * scaleX), cw - ox);
        const oh = Math.min(Math.floor(rect.height * scaleY), ch - oy);
        const cropped = cropSource.crop({
          x: ox,
          y: oy,
          width: Math.max(1, ow),
          height: Math.max(1, oh),
        });
        finish(cropped.toDataURL());
      } catch {
        finish(null);
      }
    };

    const onCancel = (_event: Electron.IpcMainEvent) => {
      if (settled || !overlay || overlay.isDestroyed()) return;
      finish(null);
    };

    const onBeforeInput = (_event: Electron.Event, input: Electron.Input) => {
      if (input.type === 'keyDown' && input.key === 'Escape') {
        finish(null);
      }
    };

    const openOverlay = (
      cap: DisplayCaptureSnapshot,
      crop: Electron.NativeImage,
      bounds: { x: number; y: number; width: number; height: number }
    ) => {
      snapshot = cap;
      cropSource = crop;

      overlay = new BrowserWindow({
        x: bounds.x,
        y: bounds.y,
        width: bounds.width,
        height: bounds.height,
        frame: false,
        transparent: true,
        fullscreenable: false,
        skipTaskbar: true,
        alwaysOnTop: true,
        focusable: true,
        show: false,
        autoHideMenuBar: true,
        backgroundColor: '#00000000',
        webPreferences: {
          preload: path.join(__dirname, 'screen-region-preload.js'),
          contextIsolation: true,
          nodeIntegration: false,
          sandbox: true,
        },
      });

      overlayWc = overlay.webContents;
      overlayWc.on('before-input-event', onBeforeInput);
      overlayWc.ipc.on(IPC_CHANNELS.SCREEN_REGION_SUBMIT, onSubmit);
      overlayWc.ipc.on(IPC_CHANNELS.SCREEN_REGION_CANCEL, onCancel);

      overlay.setIgnoreMouseEvents(false);
      overlay.loadURL(
        'data:text/html;charset=utf-8,' +
          encodeURIComponent('<!doctype html><html><head><meta charset="utf-8"/></head><body></body></html>')
      );

      overlay.on('closed', () => {
        if (!settled) finish(null);
      });

      overlay.webContents.once('did-finish-load', () => {
        if (!overlay || overlay.isDestroyed()) return;
        overlay.webContents
          .executeJavaScript(buildInjectScript(cap.dataUrl, cap.width, cap.height), true)
          .then(() => {
            overlay?.show();
            overlay?.focus();
          })
          .catch(() => {
            finish(null);
          });
      });
    };

    void (async () => {
      try {
        if (opts?.windowDataUrl) {
          const fullRes = nativeImage.createFromDataURL(opts.windowDataUrl);
          if (fullRes.isEmpty()) {
            finish(null);
            return;
          }
          const fitted = fitNativeImageToWorkArea(fullRes, display);
          const fw = fitted.getSize().width;
          const fh = fitted.getSize().height;
          const wa = display.workArea;
          const x = wa.x + Math.floor((wa.width - fw) / 2);
          const y = wa.y + Math.floor((wa.height - fh) / 2);
          openOverlay(
            { dataUrl: fitted.toDataURL(), width: fw, height: fh },
            fullRes,
            { x, y, width: fw, height: fh }
          );
          return;
        }

        const cap = await captureDisplaySnapshot(display);
        if (!cap) {
          finish(null);
          return;
        }
        const crop = nativeImage.createFromDataURL(cap.dataUrl);
        openOverlay(cap, crop, {
          x: display.bounds.x,
          y: display.bounds.y,
          width: display.bounds.width,
          height: display.bounds.height,
        });
      } catch {
        finish(null);
      }
    })();
  });
}
