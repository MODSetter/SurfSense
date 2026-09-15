# Service Worker Testing

## Table of Contents

1. [Service Worker Basics](#service-worker-basics)
2. [Registration & Lifecycle](#registration--lifecycle)
3. [Cache Testing](#cache-testing)
4. [Offline Testing](#offline-testing)
5. [Push Notifications](#push-notifications)
6. [Background Sync](#background-sync)

## Service Worker Basics

### Waiting for Service Worker Registration

```typescript
test("service worker registers", async ({ page }) => {
  await page.goto("/pwa-app");

  // Wait for SW to register
  const swRegistered = await page.evaluate(async () => {
    if (!("serviceWorker" in navigator)) return false;

    const registration = await navigator.serviceWorker.ready;
    return !!registration.active;
  });

  expect(swRegistered).toBe(true);
});
```

### Getting Service Worker State

```typescript
test("check SW state", async ({ page }) => {
  await page.goto("/");

  const swState = await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.getRegistration();
    if (!registration) return null;

    return {
      installing: !!registration.installing,
      waiting: !!registration.waiting,
      active: !!registration.active,
      scope: registration.scope,
    };
  });

  expect(swState?.active).toBe(true);
  expect(swState?.scope).toContain(page.url());
});
```

### Service Worker Context

```typescript
test("access service worker", async ({ context, page }) => {
  await page.goto("/pwa-app");

  // Get all service workers in context
  const workers = context.serviceWorkers();

  // Wait for service worker if not yet available
  if (workers.length === 0) {
    await context.waitForEvent("serviceworker");
  }

  const sw = context.serviceWorkers()[0];
  expect(sw.url()).toContain("sw.js");
});
```

## Registration & Lifecycle

### Testing SW Update Flow

```typescript
test("service worker updates", async ({ page }) => {
  await page.goto("/pwa-app");

  // Check for update
  const hasUpdate = await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready;
    await registration.update();

    return new Promise<boolean>((resolve) => {
      if (registration.waiting) {
        resolve(true);
      } else {
        registration.addEventListener("updatefound", () => {
          resolve(true);
        });
        // Timeout if no update
        setTimeout(() => resolve(false), 5000);
      }
    });
  });

  // If update found, test skip waiting flow
  if (hasUpdate) {
    await page.evaluate(async () => {
      const registration = await navigator.serviceWorker.ready;
      registration.waiting?.postMessage({ type: "SKIP_WAITING" });
    });

    // Wait for controller change
    await page.evaluate(() => {
      return new Promise<void>((resolve) => {
        navigator.serviceWorker.addEventListener("controllerchange", () => {
          resolve();
        });
      });
    });
  }
});
```

### Testing SW Installation

```typescript
test("verify SW install event", async ({ context, page }) => {
  // Listen for service worker before navigating
  const swPromise = context.waitForEvent("serviceworker");

  await page.goto("/pwa-app");

  const sw = await swPromise;

  // Evaluate in SW context
  const swVersion = await sw.evaluate(() => {
    // Access SW globals
    return (self as any).SW_VERSION || "unknown";
  });

  expect(swVersion).toBe("1.0.0");
});
```

### Unregistering Service Workers

```typescript
test.beforeEach(async ({ page }) => {
  await page.goto("/");

  // Unregister all service workers for clean state
  await page.evaluate(async () => {
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.map((r) => r.unregister()));
  });

  // Clear caches
  await page.evaluate(async () => {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames.map((name) => caches.delete(name)));
  });
});
```

## Cache Testing

### Verifying Cached Resources

```typescript
test("assets are cached", async ({ page }) => {
  await page.goto("/pwa-app");

  // Wait for SW to cache assets
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });

  // Check cache contents
  const cachedUrls = await page.evaluate(async () => {
    const cache = await caches.open("app-cache-v1");
    const requests = await cache.keys();
    return requests.map((r) => r.url);
  });

  expect(cachedUrls).toContain(expect.stringContaining("/styles.css"));
  expect(cachedUrls).toContain(expect.stringContaining("/app.js"));
});
```

### Testing Cache Strategies

```typescript
test("cache-first strategy", async ({ page }) => {
  await page.goto("/pwa-app");

  // Wait for initial cache
  await page.waitForFunction(async () => {
    const cache = await caches.open("app-cache-v1");
    const keys = await cache.keys();
    return keys.length > 0;
  });

  // Block network for cached resources
  await page.route("**/styles.css", (route) => route.abort());

  // Reload - should work from cache
  await page.reload();

  // Verify page still styled (CSS loaded from cache)
  const hasStyles = await page.evaluate(() => {
    const body = document.body;
    const styles = window.getComputedStyle(body);
    return styles.fontFamily !== ""; // Has custom font from CSS
  });

  expect(hasStyles).toBe(true);
});
```

### Testing Cache Updates

```typescript
test("cache updates on new version", async ({ page }) => {
  await page.goto("/pwa-app");

  // Get initial cache
  const initialCacheKeys = await page.evaluate(async () => {
    const cache = await caches.open("app-cache-v1");
    const keys = await cache.keys();
    return keys.map((r) => r.url);
  });

  // Simulate app update by mocking SW response
  await page.route("**/sw.js", (route) => {
    route.fulfill({
      contentType: "application/javascript",
      body: `
        const VERSION = 'v2';
        self.addEventListener('install', (e) => {
          e.waitUntil(caches.open('app-cache-v2'));
          self.skipWaiting();
        });
      `,
    });
  });

  // Trigger update
  await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready;
    await reg.update();
  });

  // Verify new cache exists
  await page.waitForFunction(async () => {
    return await caches.has("app-cache-v2");
  });
});
```

## Offline Testing

This section covers **offline-first apps (PWAs)** that are designed to work offline using service workers, caching, and background sync. For testing **unexpected network failures** (error recovery, graceful degradation), see [error-testing.md](error-testing.md#offline-testing).

### Simulating Offline Mode

```typescript
test("app works offline", async ({ page, context }) => {
  await page.goto("/pwa-app");

  // Ensure SW is active and content cached
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.waitForTimeout(1000); // Allow caching to complete

  // Go offline
  await context.setOffline(true);

  // Navigate to cached page
  await page.reload();

  // Verify content loads
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  // Verify offline indicator
  await expect(page.locator(".offline-badge")).toBeVisible();

  // Go back online
  await context.setOffline(false);
  await expect(page.locator(".offline-badge")).not.toBeVisible();
});
```

### Testing Offline Fallback

```typescript
test("shows offline page for uncached routes", async ({ page, context }) => {
  await page.goto("/pwa-app");
  await page.evaluate(() => navigator.serviceWorker.ready);

  // Go offline
  await context.setOffline(true);

  // Navigate to uncached page
  await page.goto("/uncached-page");

  // Should show offline fallback
  await expect(page.getByText("You are offline")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});
```

### Testing Offline Form Submission

```typescript
test("queues form submission offline", async ({ page, context }) => {
  await page.goto("/pwa-app/form");

  // Go offline
  await context.setOffline(true);

  // Submit form
  await page.getByLabel("Message").fill("Offline message");
  await page.getByRole("button", { name: "Send" }).click();

  // Should show queued status
  await expect(page.getByText("Queued for sync")).toBeVisible();

  // Go online
  await context.setOffline(false);

  // Trigger sync (or wait for automatic)
  await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready;
    // Manually trigger sync for testing
    await (reg as any).sync?.register("form-sync");
  });

  // Verify submission completed
  await expect(page.getByText("Message sent")).toBeVisible({ timeout: 10000 });
});
```

## Push Notifications

### Mocking Push Subscription

```typescript
test("handles push subscription", async ({ page, context }) => {
  // Grant notification permission
  await context.grantPermissions(["notifications"]);

  await page.goto("/pwa-app");

  // Subscribe to push
  const subscription = await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: "test-key",
    });
    return sub.toJSON();
  });

  expect(subscription.endpoint).toBeDefined();
});
```

### Testing Push Message Handling

```typescript
test("handles push notification", async ({ context, page }) => {
  await context.grantPermissions(["notifications"]);
  await page.goto("/pwa-app");

  // Wait for SW
  const swPromise = context.waitForEvent("serviceworker");
  const sw = await swPromise;

  // Simulate push message to service worker
  await sw.evaluate(async () => {
    // Dispatch push event
    const pushEvent = new PushEvent("push", {
      data: new PushMessageData(
        JSON.stringify({ title: "Test", body: "Push message" }),
      ),
    });
    self.dispatchEvent(pushEvent);
  });

  // Note: Actual notification display testing is limited in Playwright
  // Focus on verifying the SW handles the push correctly
});
```

### Testing Notification Click

```typescript
test("notification click opens page", async ({ context, page }) => {
  await context.grantPermissions(["notifications"]);
  await page.goto("/pwa-app");

  // Store notification URL target
  let notificationUrl = "";

  // Listen for new pages (notification click opens new page)
  context.on("page", (newPage) => {
    notificationUrl = newPage.url();
  });

  // Trigger notification via SW
  await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready;
    await reg.showNotification("Test", {
      body: "Click me",
      data: { url: "/notification-target" },
    });
  });

  // Simulate clicking notification (via SW)
  const sw = context.serviceWorkers()[0];
  await sw.evaluate(() => {
    self.dispatchEvent(
      new NotificationEvent("notificationclick", {
        notification: { data: { url: "/notification-target" } } as any,
      }),
    );
  });

  // Verify navigation occurred
  await page.waitForTimeout(1000);
  // Check if new page opened or current page navigated
});
```

## Background Sync

### Testing Background Sync Registration

```typescript
test("registers background sync", async ({ page }) => {
  await page.goto("/pwa-app");

  // Register sync
  const syncRegistered = await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready;
    if (!("sync" in reg)) return false;

    await (reg as any).sync.register("my-sync");
    return true;
  });

  expect(syncRegistered).toBe(true);
});
```

### Testing Sync Event

```typescript
test("sync event fires when online", async ({ context, page }) => {
  await page.goto("/pwa-app");

  // Queue data while offline
  await context.setOffline(true);

  await page.evaluate(async () => {
    // Store data in IndexedDB for sync
    const db = await openDB();
    await db.put("sync-queue", { id: 1, data: "test" });

    // Register sync
    const reg = await navigator.serviceWorker.ready;
    await (reg as any).sync.register("data-sync");
  });

  // Track sync completion
  await page.evaluate(() => {
    window.syncCompleted = false;
    navigator.serviceWorker.addEventListener("message", (e) => {
      if (e.data.type === "SYNC_COMPLETE") {
        window.syncCompleted = true;
      }
    });
  });

  // Go online
  await context.setOffline(false);

  // Wait for sync to complete
  await page.waitForFunction(() => window.syncCompleted, { timeout: 10000 });
});
```

## Anti-Patterns to Avoid

| Anti-Pattern                   | Problem                 | Solution                                     |
| ------------------------------ | ----------------------- | -------------------------------------------- |
| Not clearing SW between tests  | Tests affect each other | Unregister SW in beforeEach                  |
| Not waiting for SW ready       | Race conditions         | Always await `navigator.serviceWorker.ready` |
| Testing in isolation only      | Misses real SW behavior | Test with actual caching                     |
| Hardcoded timeouts for caching | Flaky tests             | Wait for cache to populate                   |
| Ignoring SW update cycle       | Missing update bugs     | Test install, activate, update flows         |

## Related References

- **Network Failures**: See [error-testing.md](error-testing.md#offline-testing) for unexpected network failure patterns
- **Browser APIs**: See [browser-apis.md](browser-apis.md) for permissions
- **Network Mocking**: See [network-advanced.md](../advanced/network-advanced.md) for network interception
- **Browser Extensions**: See [browser-extensions.md](../testing-patterns/browser-extensions.md) for extension service worker patterns
