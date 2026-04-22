import { PostHog } from 'posthog-node';
import { machineIdSync } from 'node-machine-id';
import { app } from 'electron';

let client: PostHog | null = null;
let machineId = '';
let currentDistinctId = '';
let identifiedUserId: string | null = null;

function baseProperties(): Record<string, unknown> {
  return {
    platform: 'desktop',
    app_version: app.getVersion(),
    os: process.platform,
    arch: process.arch,
    machine_id: machineId,
  };
}

export function initAnalytics(): void {
  const key = process.env.POSTHOG_KEY;
  if (!key) return;

  try {
    machineId = machineIdSync(true);
    currentDistinctId = machineId;
  } catch {
    return;
  }

  client = new PostHog(key, {
    host: process.env.POSTHOG_HOST || 'https://assets.surfsense.com',
    flushAt: 20,
    flushInterval: 10000,
  });
}

export function getMachineId(): string {
  return machineId;
}

export function getDistinctId(): string {
  return currentDistinctId;
}

/**
 * Identify the current logged-in user in PostHog so main-process desktop
 * events (and linked anonymous machine events) are attributed to that person.
 *
 * Idempotent: calling identify repeatedly with the same userId is a no-op.
 */
export function identifyUser(
  userId: string,
  properties?: Record<string, unknown>
): void {
  if (!client || !userId) return;
  if (identifiedUserId === userId) {
    // Already identified — only refresh person properties
    try {
      client.identify({
        distinctId: userId,
        properties: {
          ...baseProperties(),
          $set: {
            ...(properties || {}),
            platform: 'desktop',
            last_seen_at: new Date().toISOString(),
          },
        },
      });
    } catch {
      // ignore
    }
    return;
  }

  try {
    // Link the anonymous machine distinct ID to the authenticated user
    client.identify({
      distinctId: userId,
      properties: {
        ...baseProperties(),
        $anon_distinct_id: machineId,
        $set: {
          ...(properties || {}),
          platform: 'desktop',
          last_seen_at: new Date().toISOString(),
        },
        $set_once: {
          first_seen_platform: 'desktop',
        },
      },
    });

    identifiedUserId = userId;
    currentDistinctId = userId;
  } catch {
    // Analytics must never break the app
  }
}

/**
 * Reset user identity on logout. Subsequent events are captured anonymously
 * against the machine ID until the user logs in again.
 */
export function resetUser(): void {
  if (!client) return;
  identifiedUserId = null;
  currentDistinctId = machineId;
}

export function trackEvent(
  event: string,
  properties?: Record<string, unknown>
): void {
  if (!client) return;

  try {
    client.capture({
      distinctId: currentDistinctId || machineId,
      event,
      properties: {
        ...baseProperties(),
        ...properties,
      },
    });
  } catch {
    // Analytics should never break the app
  }
}

export async function shutdownAnalytics(): Promise<void> {
  if (!client) return;

  const timeout = new Promise<void>((resolve) => setTimeout(resolve, 3000));
  await Promise.race([client.shutdown(), timeout]);
  client = null;
}
