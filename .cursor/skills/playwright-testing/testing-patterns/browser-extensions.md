# Browser Extension Testing

## Table of Contents

1. [Setup & Configuration](#setup--configuration)
2. [Loading Extensions](#loading-extensions)
3. [Popup Testing](#popup-testing)
4. [Background Script Testing](#background-script-testing)
5. [Content Script Testing](#content-script-testing)
6. [Extension APIs](#extension-apis)
7. [Cross-Browser Testing](#cross-browser-testing)

## Setup & Configuration

### Prerequisites

```bash
npm install -D @playwright/test
npx playwright install chromium  # Extensions only work in Chromium
```

### Basic Configuration

```typescript
// playwright.config.ts
import { defineConfig } from "@playwright/test";
import path from "path";

export default defineConfig({
  testDir: "./tests",
  use: {
    // Extensions require non-headless Chromium
    headless: false,
  },
  projects: [
    {
      name: "chromium-extension",
      use: {
        browserName: "chromium",
      },
    },
  ],
});
```

### Extension Fixture

```typescript
// fixtures/extension.ts
import { test as base, chromium, BrowserContext, Page } from "@playwright/test";
import path from "path";

type ExtensionFixtures = {
  context: BrowserContext;
  extensionId: string;
  backgroundPage: Page;
};

export const test = base.extend<ExtensionFixtures>({
  context: async ({}, use) => {
    const pathToExtension = path.join(__dirname, "../extension");

    const context = await chromium.launchPersistentContext("", {
      headless: false,
      args: [
        `--disable-extensions-except=${pathToExtension}`,
        `--load-extension=${pathToExtension}`,
      ],
    });

    await use(context);
    await context.close();
  },

  extensionId: async ({ context }, use) => {
    // Get extension ID from service worker URL
    let extensionId = "";

    // Wait for service worker to be registered
    const serviceWorker =
      context.serviceWorkers()[0] ||
      (await context.waitForEvent("serviceworker"));

    extensionId = serviceWorker.url().split("/")[2];

    await use(extensionId);
  },

  backgroundPage: async ({ context }, use) => {
    // For Manifest V2 extensions
    const backgroundPage =
      context.backgroundPages()[0] ||
      (await context.waitForEvent("backgroundpage"));

    await use(backgroundPage);
  },
});

export { expect } from "@playwright/test";
```

## Loading Extensions

### Manifest V3 (Service Worker)

```typescript
test("load MV3 extension", async () => {
  const pathToExtension = path.join(__dirname, "../my-extension");

  const context = await chromium.launchPersistentContext("", {
    headless: false,
    args: [
      `--disable-extensions-except=${pathToExtension}`,
      `--load-extension=${pathToExtension}`,
    ],
  });

  // Wait for service worker
  const serviceWorker = await context.waitForEvent("serviceworker");
  expect(serviceWorker.url()).toContain("chrome-extension://");

  await context.close();
});
```

### Manifest V2 (Background Page)

```typescript
test("load MV2 extension", async () => {
  const pathToExtension = path.join(__dirname, "../my-extension-v2");

  const context = await chromium.launchPersistentContext("", {
    headless: false,
    args: [
      `--disable-extensions-except=${pathToExtension}`,
      `--load-extension=${pathToExtension}`,
    ],
  });

  // Wait for background page
  const backgroundPage = await context.waitForEvent("backgroundpage");
  expect(backgroundPage.url()).toContain("chrome-extension://");

  await context.close();
});
```

### Multiple Extensions

```typescript
test("load multiple extensions", async () => {
  const extension1 = path.join(__dirname, "../extension1");
  const extension2 = path.join(__dirname, "../extension2");

  const context = await chromium.launchPersistentContext("", {
    headless: false,
    args: [
      `--disable-extensions-except=${extension1},${extension2}`,
      `--load-extension=${extension1},${extension2}`,
    ],
  });

  // Both service workers should be available
  await context.waitForEvent("serviceworker");
  await context.waitForEvent("serviceworker");

  expect(context.serviceWorkers().length).toBe(2);

  await context.close();
});
```

## Popup Testing

### Opening Extension Popup

```typescript
test("test popup UI", async ({ context, extensionId }) => {
  // Open popup directly by URL
  const popupPage = await context.newPage();
  await popupPage.goto(`chrome-extension://${extensionId}/popup.html`);

  // Test popup interactions
  await expect(popupPage.getByRole("heading")).toHaveText("My Extension");
  await popupPage.getByRole("button", { name: "Enable" }).click();
  await expect(popupPage.getByText("Enabled")).toBeVisible();
});
```

### Popup State Persistence

```typescript
test("popup remembers state", async ({ context, extensionId }) => {
  // First interaction
  const popup1 = await context.newPage();
  await popup1.goto(`chrome-extension://${extensionId}/popup.html`);
  await popup1.getByRole("checkbox", { name: "Dark Mode" }).check();
  await popup1.close();

  // Reopen popup
  const popup2 = await context.newPage();
  await popup2.goto(`chrome-extension://${extensionId}/popup.html`);

  // State should persist
  await expect(
    popup2.getByRole("checkbox", { name: "Dark Mode" }),
  ).toBeChecked();
});
```

### Popup Communication with Background

```typescript
test("popup sends message to background", async ({ context, extensionId }) => {
  const popup = await context.newPage();
  await popup.goto(`chrome-extension://${extensionId}/popup.html`);

  // Set up listener for response
  const responsePromise = popup.evaluate(() => {
    return new Promise((resolve) => {
      chrome.runtime.onMessage.addListener((message) => {
        if (message.type === "RESPONSE") resolve(message.data);
      });
    });
  });

  // Click button that sends message
  await popup.getByRole("button", { name: "Fetch Data" }).click();

  // Verify response
  const response = await responsePromise;
  expect(response).toBeDefined();
});
```

## Background Script Testing

### Manifest V3 Service Worker

```typescript
test("service worker handles messages", async ({ context, extensionId }) => {
  const page = await context.newPage();
  await page.goto("https://example.com");

  // Send message to service worker from page
  const response = await page.evaluate(async (extId) => {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(extId, { type: "GET_STATUS" }, resolve);
    });
  }, extensionId);

  expect(response).toEqual({ status: "active" });
});
```

### Testing Background Logic

```typescript
test("background script logic", async ({ context }) => {
  const serviceWorker =
    context.serviceWorkers()[0] ||
    (await context.waitForEvent("serviceworker"));

  // Evaluate in service worker context
  const result = await serviceWorker.evaluate(async () => {
    // Access extension APIs
    const storage = await chrome.storage.local.get("settings");
    return storage;
  });

  expect(result.settings).toBeDefined();
});
```

### Alarms and Timers

```typescript
test("alarm triggers correctly", async ({ context }) => {
  const serviceWorker = await context.waitForEvent("serviceworker");

  // Create alarm
  await serviceWorker.evaluate(async () => {
    await chrome.alarms.create("test-alarm", { delayInMinutes: 0.01 });
  });

  // Wait for alarm handler
  await serviceWorker.evaluate(() => {
    return new Promise<void>((resolve) => {
      chrome.alarms.onAlarm.addListener((alarm) => {
        if (alarm.name === "test-alarm") resolve();
      });
    });
  });

  // Verify alarm was handled (check side effects)
  const wasHandled = await serviceWorker.evaluate(async () => {
    const { alarmTriggered } = await chrome.storage.local.get("alarmTriggered");
    return alarmTriggered;
  });

  expect(wasHandled).toBe(true);
});
```

## Content Script Testing

### Injected Content Script

```typescript
test("content script injects UI", async ({ context }) => {
  const page = await context.newPage();
  await page.goto("https://example.com");

  // Wait for content script to inject elements
  await expect(page.locator("#my-extension-widget")).toBeVisible();

  // Interact with injected UI
  await page.locator("#my-extension-widget button").click();
  await expect(page.locator("#my-extension-widget .result")).toHaveText(
    "Success",
  );
});
```

### Content Script Communication

```typescript
test("content script communicates with background", async ({
  context,
  extensionId,
}) => {
  const page = await context.newPage();
  await page.goto("https://example.com");

  // Trigger content script action
  await page.locator("#my-extension-button").click();

  // Wait for background response reflected in UI
  await expect(page.locator("#my-extension-status")).toHaveText("Connected");
});
```

### Page Modification Testing

```typescript
test("content script modifies page", async ({ context }) => {
  const page = await context.newPage();
  await page.goto("https://example.com");

  // Verify content script modifications
  const hasModification = await page.evaluate(() => {
    // Check for injected styles
    const styles = document.querySelectorAll('style[data-extension="my-ext"]');
    return styles.length > 0;
  });

  expect(hasModification).toBe(true);

  // Check DOM modifications
  const modifiedElements = await page
    .locator("[data-modified-by-extension]")
    .count();
  expect(modifiedElements).toBeGreaterThan(0);
});
```

## Extension APIs

### Storage API

```typescript
test("chrome.storage operations", async ({ context }) => {
  const serviceWorker = await context.waitForEvent("serviceworker");

  // Set storage
  await serviceWorker.evaluate(async () => {
    await chrome.storage.local.set({ key: "value", count: 42 });
  });

  // Get storage
  const data = await serviceWorker.evaluate(async () => {
    return await chrome.storage.local.get(["key", "count"]);
  });

  expect(data).toEqual({ key: "value", count: 42 });

  // Test storage.sync
  await serviceWorker.evaluate(async () => {
    await chrome.storage.sync.set({ synced: true });
  });

  const syncData = await serviceWorker.evaluate(async () => {
    return await chrome.storage.sync.get("synced");
  });

  expect(syncData.synced).toBe(true);
});
```

### Tabs API

```typescript
test("chrome.tabs operations", async ({ context }) => {
  const serviceWorker = await context.waitForEvent("serviceworker");

  // Create a tab
  const page = await context.newPage();
  await page.goto("https://example.com");

  // Query tabs from service worker
  const tabs = await serviceWorker.evaluate(async () => {
    return await chrome.tabs.query({ url: "*://example.com/*" });
  });

  expect(tabs.length).toBeGreaterThan(0);
  expect(tabs[0].url).toContain("example.com");

  // Send message to tab
  await serviceWorker.evaluate(async (tabId) => {
    await chrome.tabs.sendMessage(tabId, { type: "PING" });
  }, tabs[0].id);
});
```

### Context Menus

```typescript
test("context menu actions", async ({ context, extensionId }) => {
  const serviceWorker = await context.waitForEvent("serviceworker");

  // Create context menu
  await serviceWorker.evaluate(async () => {
    await chrome.contextMenus.create({
      id: "test-menu",
      title: "Test Action",
      contexts: ["selection"],
    });
  });

  // Simulate context menu click
  const page = await context.newPage();
  await page.goto("https://example.com");

  // Select text
  await page.evaluate(() => {
    const range = document.createRange();
    range.selectNodeContents(document.body.firstChild!);
    window.getSelection()?.addRange(range);
  });

  // Trigger context menu action programmatically
  await serviceWorker.evaluate(async () => {
    // Simulate the click handler
    chrome.contextMenus.onClicked.dispatch(
      { menuItemId: "test-menu", selectionText: "selected text" },
      { id: 1, url: "https://example.com" },
    );
  });
});
```

### Permissions API

```typescript
test("request permissions", async ({ context, extensionId }) => {
  const popup = await context.newPage();
  await popup.goto(`chrome-extension://${extensionId}/popup.html`);

  // Check current permissions
  const hasPermission = await popup.evaluate(async () => {
    return await chrome.permissions.contains({
      origins: ["https://*.github.com/*"],
    });
  });

  // Request new permission (will show prompt in real scenario)
  // For testing, we check the request is made correctly
  const permissionRequest = popup.evaluate(async () => {
    try {
      return await chrome.permissions.request({
        origins: ["https://*.github.com/*"],
      });
    } catch (e) {
      return false;
    }
  });

  // In automated tests, permission prompts are typically auto-granted or mocked
});
```

## Anti-Patterns to Avoid

| Anti-Pattern                   | Problem               | Solution                                 |
| ------------------------------ | --------------------- | ---------------------------------------- |
| Testing in headless mode       | Extensions don't load | Use `headless: false`                    |
| Not waiting for service worker | Race conditions       | Wait for `serviceworker` event           |
| Hardcoding extension ID        | ID changes on reload  | Extract ID from service worker URL       |
| Testing packed extensions only | Slow iteration        | Test unpacked during development         |
| Ignoring MV3 differences       | Breaking changes      | Test both MV2 and MV3 if supporting both |

## Related References

- **Service Workers**: See [service-workers.md](../browser-apis/service-workers.md) for SW testing patterns
- **Multi-Context**: See [multi-context.md](../advanced/multi-context.md) for popup handling
- **Browser APIs**: See [browser-apis.md](../browser-apis/browser-apis.md) for permissions testing
