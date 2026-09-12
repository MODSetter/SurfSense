const DEFAULT_SUNSET_URL = 'https://surfsense.com/sunset';
const TIMEOUT_MS = 3000;

let sunsetUrl: string | null = null;

export async function checkSunset(): Promise<void> {
  const backendUrl = process.env.SURFSENSE_BACKEND_INTERNAL_URL || process.env.HOSTED_BACKEND_URL;
  if (!backendUrl) return;
  try {
    const res = await fetch(`${backendUrl.replace(/\/$/, '')}/health`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!res.ok) return;
    const body = (await res.json()) as { sunset?: unknown; sunset_url?: unknown };
    if (body.sunset !== true) return;
    sunsetUrl = typeof body.sunset_url === 'string' && body.sunset_url ? body.sunset_url : DEFAULT_SUNSET_URL;
  } catch {
    // fail open
  }
}

export function getSunsetUrl(): string | null {
  return sunsetUrl;
}
