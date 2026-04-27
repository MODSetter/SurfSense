import { IPC_CHANNELS } from '../ipc/channels';
import { trackEvent } from './analytics';
import { pickScreenRegion } from './screen-region-picker';
import { getMainWindow, showMainWindow } from './window';
import { hasScreenRecordingPermission, requestScreenRecording } from './permissions';

export async function runScreenshotAssistShortcut(): Promise<void> {
  showMainWindow('shortcut');
  await new Promise((r) => setTimeout(r, 400));
  if (!hasScreenRecordingPermission()) {
    requestScreenRecording();
    return;
  }
  const url = await pickScreenRegion();
  const mw = getMainWindow();
  if (url && mw && !mw.isDestroyed()) {
    mw.webContents.send(IPC_CHANNELS.CHAT_SCREEN_CAPTURE, url);
    trackEvent('desktop_screenshot_assist_region_to_chat', {});
  }
}
