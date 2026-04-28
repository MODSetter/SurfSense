/**
 * Window capture for Screenshot Assist and chat fullscreen: single-session
 * desktopCapturer, region overlay, and shortcut entry point.
 */
export { pickOpenWindowCapture, type PickedWindowResult } from './window-picker';
export { pickScreenRegion, captureCurrentDisplayDataUrl } from './screen-region-picker';
export { runScreenshotAssistShortcut } from './screenshot-assist';
