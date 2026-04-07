import { PostHog } from 'posthog-node';
import { machineIdSync } from 'node-machine-id';
import { app } from 'electron';

let client: PostHog | null = null;
let distinctId = '';

export function initAnalytics(): void {
  const key = process.env.POSTHOG_KEY;
  if (!key) return;

  try {
    distinctId = machineIdSync(true);
  } catch {
    return;
  }

  client = new PostHog(key, {
    host: process.env.POSTHOG_HOST || 'https://us.i.posthog.com',
    flushAt: 20,
    flushInterval: 10000,
  });
}

export function trackEvent(event: string, properties?: Record<string, unknown>): void {
  if (!client) return;

  client.capture({
    distinctId,
    event,
    properties: {
      platform: 'desktop',
      app_version: app.getVersion(),
      os: process.platform,
      ...properties,
    },
  });
}

export async function shutdownAnalytics(): Promise<void> {
  if (!client) return;

  const timeout = new Promise<void>((resolve) => setTimeout(resolve, 3000));
  await Promise.race([client.shutdown(), timeout]);
  client = null;
}
