import { desktopCapturer, screen } from 'electron';

/**
 * Captures the primary display as a base64-encoded PNG data URL.
 * Uses the display's actual size for full-resolution capture.
 */
export async function captureScreen(): Promise<string | null> {
  try {
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.size;

    const sources = await desktopCapturer.getSources({
      types: ['screen'],
      thumbnailSize: { width, height },
    });

    if (!sources.length) {
      console.error('[screenshot] No screen sources found');
      return null;
    }

    return sources[0].thumbnail.toDataURL();
  } catch (err) {
    console.error('[screenshot] Failed to capture screen:', err);
    return null;
  }
}
