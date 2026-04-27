import { IPC_CHANNELS } from '../ipc/channels';
import { trackEvent } from './analytics';
import { pickScreenRegion } from './screen-region-picker';
import { pickOpenWindowCapture } from './window-picker';
import { getMainWindow, showMainWindow } from './window';
import { hasScreenRecordingPermission, requestScreenRecording } from './permissions';

export async function runScreenshotAssistShortcut(): Promise<void> {
  if (!hasScreenRecordingPermission()) {
    requestScreenRecording();
    return;
  }

  const picked = await pickOpenWindowCapture();
  if (!picked) return;

  const url = await pickScreenRegion({ windowDataUrl: picked.dataUrl });
  if (!url) return;

  showMainWindow('shortcut');
  const mw = getMainWindow();
  if (mw && !mw.isDestroyed()) {
    mw.webContents.send(IPC_CHANNELS.CHAT_SCREEN_CAPTURE, url);
    trackEvent('desktop_screenshot_assist_region_to_chat', {});
  }
}
