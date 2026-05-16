# Electron Testing

## Table of Contents

1. [Setup & Configuration](#setup--configuration)
2. [Launching Electron Apps](#launching-electron-apps)
3. [Main Process Testing](#main-process-testing)
4. [Renderer Process Testing](#renderer-process-testing)
5. [IPC Communication](#ipc-communication)
6. [Native Features](#native-features)
7. [Packaging & Distribution](#packaging--distribution)

## Setup & Configuration

### Installation

```bash
npm install -D @playwright/test electron
```

### Basic Configuration

```typescript
// playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30000,
  use: {
    trace: "on-first-retry",
  },
});
```

### Electron Test Fixture

```typescript
// fixtures/electron.ts
import {
  test as base,
  _electron as electron,
  ElectronApplication,
  Page,
} from "@playwright/test";

type ElectronFixtures = {
  electronApp: ElectronApplication;
  window: Page;
};

export const test = base.extend<ElectronFixtures>({
  electronApp: async ({}, use) => {
    // Launch Electron app
    const electronApp = await electron.launch({
      args: [".", "--no-sandbox"],
      env: {
        ...process.env,
        NODE_ENV: "test",
      },
    });

    await use(electronApp);

    // Cleanup
    await electronApp.close();
  },

  window: async ({ electronApp }, use) => {
    // Wait for first window
    const window = await electronApp.firstWindow();

    // Wait for app to be ready
    await window.waitForLoadState("domcontentloaded");

    await use(window);
  },
});

export { expect } from "@playwright/test";
```

### Launch Options

```typescript
// Advanced launch configuration
const electronApp = await electron.launch({
  args: ["main.js", "--custom-flag"],
  cwd: "/path/to/app",
  env: {
    ...process.env,
    ELECTRON_ENABLE_LOGGING: "1",
    NODE_ENV: "test",
  },
  timeout: 30000,
  // For packaged apps
  executablePath: "/path/to/MyApp.app/Contents/MacOS/MyApp",
});
```

## Launching Electron Apps

### Development Mode

```typescript
test("launch in dev mode", async () => {
  const electronApp = await electron.launch({
    args: ["."], // Points to package.json main
  });

  const window = await electronApp.firstWindow();
  await expect(window.locator("h1")).toContainText("My App");

  await electronApp.close();
});
```

### Packaged Application

```typescript
test("launch packaged app", async () => {
  const appPath =
    process.platform === "darwin"
      ? "/Applications/MyApp.app/Contents/MacOS/MyApp"
      : process.platform === "win32"
        ? "C:\\Program Files\\MyApp\\MyApp.exe"
        : "/usr/bin/myapp";

  const electronApp = await electron.launch({
    executablePath: appPath,
  });

  const window = await electronApp.firstWindow();
  await expect(window).toHaveTitle(/MyApp/);

  await electronApp.close();
});
```

### Multiple Windows

```typescript
test("handle multiple windows", async ({ electronApp }) => {
  const mainWindow = await electronApp.firstWindow();

  // Trigger new window
  await mainWindow.getByRole("button", { name: "Open Settings" }).click();

  // Wait for new window
  const settingsWindow = await electronApp.waitForEvent("window");

  // Both windows are now accessible
  await expect(settingsWindow.locator("h1")).toHaveText("Settings");
  await expect(mainWindow.locator("h1")).toHaveText("Main");

  // Get all windows
  const windows = electronApp.windows();
  expect(windows.length).toBe(2);
});
```

## Main Process Testing

### Evaluate in Main Process

```typescript
test("access main process", async ({ electronApp }) => {
  // Evaluate in main process context
  const appPath = await electronApp.evaluate(async ({ app }) => {
    return app.getAppPath();
  });

  expect(appPath).toContain("my-electron-app");
});
```

### Access Electron APIs

```typescript
test("electron API access", async ({ electronApp }) => {
  // Get app version
  const version = await electronApp.evaluate(async ({ app }) => {
    return app.getVersion();
  });
  expect(version).toMatch(/^\d+\.\d+\.\d+$/);

  // Get platform info
  const platform = await electronApp.evaluate(async ({ app }) => {
    return process.platform;
  });
  expect(["darwin", "win32", "linux"]).toContain(platform);

  // Check if app is ready
  const isReady = await electronApp.evaluate(async ({ app }) => {
    return app.isReady();
  });
  expect(isReady).toBe(true);
});
```

### BrowserWindow Properties

```typescript
test("check window properties", async ({ electronApp, window }) => {
  // Get BrowserWindow from main process
  const windowBounds = await electronApp.evaluate(async ({ BrowserWindow }) => {
    const win = BrowserWindow.getAllWindows()[0];
    return win.getBounds();
  });

  expect(windowBounds.width).toBeGreaterThan(0);
  expect(windowBounds.height).toBeGreaterThan(0);

  // Check window state
  const isMaximized = await electronApp.evaluate(async ({ BrowserWindow }) => {
    const win = BrowserWindow.getAllWindows()[0];
    return win.isMaximized();
  });

  // Check window title
  const title = await electronApp.evaluate(async ({ BrowserWindow }) => {
    const win = BrowserWindow.getAllWindows()[0];
    return win.getTitle();
  });
  expect(title).toBeTruthy();
});
```

## Renderer Process Testing

### Standard Page Testing

```typescript
test("renderer interactions", async ({ window }) => {
  // Standard Playwright page interactions
  await window.getByRole("button", { name: "Click Me" }).click();
  await expect(window.getByText("Clicked!")).toBeVisible();

  // Fill forms
  await window.getByLabel("Username").fill("testuser");
  await window.getByLabel("Password").fill("password123");
  await window.getByRole("button", { name: "Login" }).click();

  // Verify navigation
  await expect(window).toHaveURL(/dashboard/);
});
```

### Access Node.js in Renderer

```typescript
test("node integration", async ({ window }) => {
  // If nodeIntegration is enabled
  const nodeVersion = await window.evaluate(() => {
    return (window as any).process?.version;
  });

  // Check if Node APIs are available
  const hasFs = await window.evaluate(() => {
    return typeof (window as any).require === "function";
  });
});
```

### Context Isolation Testing

```typescript
test("context isolation", async ({ window }) => {
  // Test preload script exposed APIs
  const apiAvailable = await window.evaluate(() => {
    return typeof (window as any).electronAPI !== "undefined";
  });
  expect(apiAvailable).toBe(true);

  // Call exposed API
  const result = await window.evaluate(async () => {
    return await (window as any).electronAPI.getAppVersion();
  });
  expect(result).toMatch(/^\d+\.\d+\.\d+$/);
});
```

## IPC Communication

### Testing IPC from Renderer

```typescript
test("IPC invoke", async ({ window }) => {
  // Test preload-exposed IPC call
  const result = await window.evaluate(async () => {
    return await (window as any).electronAPI.getData("user-settings");
  });

  expect(result).toHaveProperty("theme");
});
```

### Testing IPC from Main Process

```typescript
test("main to renderer IPC", async ({ electronApp, window }) => {
  // Set up listener in renderer
  await window.evaluate(() => {
    (window as any).receivedMessage = null;
    (window as any).electronAPI.onMessage((msg: string) => {
      (window as any).receivedMessage = msg;
    });
  });

  // Send from main process
  await electronApp.evaluate(async ({ BrowserWindow }) => {
    const win = BrowserWindow.getAllWindows()[0];
    win.webContents.send("message", "Hello from main!");
  });

  // Verify receipt
  await window.waitForFunction(() => (window as any).receivedMessage !== null);
  const message = await window.evaluate(() => (window as any).receivedMessage);
  expect(message).toBe("Hello from main!");
});
```

### Mock IPC Handlers

```typescript
// In test setup or fixture
test("mock IPC handler", async ({ electronApp, window }) => {
  // Override IPC handler in main process
  await electronApp.evaluate(async ({ ipcMain }) => {
    // Remove existing handler
    ipcMain.removeHandler("fetch-data");

    // Add mock handler
    ipcMain.handle("fetch-data", async () => {
      return { mocked: true, data: "test-data" };
    });
  });

  // Test with mocked handler
  const result = await window.evaluate(async () => {
    return await (window as any).electronAPI.fetchData();
  });

  expect(result.mocked).toBe(true);
});
```

## Native Features

### File System Dialogs

```typescript
test("file dialog", async ({ electronApp, window }) => {
  // Mock dialog response
  await electronApp.evaluate(async ({ dialog }) => {
    dialog.showOpenDialog = async () => ({
      canceled: false,
      filePaths: ["/mock/path/file.txt"],
    });
  });

  // Trigger file open
  await window.getByRole("button", { name: "Open File" }).click();

  // Verify file was "opened"
  await expect(window.getByText("file.txt")).toBeVisible();
});

test("save dialog", async ({ electronApp, window }) => {
  await electronApp.evaluate(async ({ dialog }) => {
    dialog.showSaveDialog = async () => ({
      canceled: false,
      filePath: "/mock/path/saved-file.txt",
    });
  });

  await window.getByRole("button", { name: "Save" }).click();
  await expect(window.getByText("Saved successfully")).toBeVisible();
});
```

### Menu Testing

```typescript
test("application menu", async ({ electronApp }) => {
  // Get menu structure
  const menuLabels = await electronApp.evaluate(async ({ Menu }) => {
    const menu = Menu.getApplicationMenu();
    return menu?.items.map((item) => item.label) || [];
  });

  expect(menuLabels).toContain("File");
  expect(menuLabels).toContain("Edit");

  // Trigger menu action
  await electronApp.evaluate(async ({ Menu }) => {
    const menu = Menu.getApplicationMenu();
    const fileMenu = menu?.items.find((item) => item.label === "File");
    const newItem = fileMenu?.submenu?.items.find(
      (item) => item.label === "New",
    );
    newItem?.click();
  });
});
```

### Native Notifications

```typescript
test("notifications", async ({ electronApp, window }) => {
  // Mock Notification
  let notificationShown = false;
  await electronApp.evaluate(async ({ Notification }) => {
    const OriginalNotification = Notification;
    (global as any).Notification = class extends OriginalNotification {
      constructor(options: any) {
        super(options);
        (global as any).lastNotification = options;
      }
    };
  });

  // Trigger notification
  await window.getByRole("button", { name: "Notify" }).click();

  // Verify notification was created
  const notification = await electronApp.evaluate(async () => {
    return (global as any).lastNotification;
  });

  expect(notification.title).toBe("New Message");
});
```

### Clipboard

```typescript
test("clipboard operations", async ({ electronApp, window }) => {
  // Write to clipboard
  await electronApp.evaluate(async ({ clipboard }) => {
    clipboard.writeText("Test clipboard content");
  });

  // Paste in app
  await window.getByRole("textbox").focus();
  await window.keyboard.press("ControlOrMeta+v");

  // Read clipboard
  const clipboardContent = await electronApp.evaluate(async ({ clipboard }) => {
    return clipboard.readText();
  });

  expect(clipboardContent).toBe("Test clipboard content");
});
```

## Packaging & Distribution

### Testing Packaged Apps

```typescript
// fixtures/packaged-electron.ts
import { test as base, _electron as electron } from "@playwright/test";
import path from "path";
import { execSync } from "child_process";

export const test = base.extend({
  electronApp: async ({}, use) => {
    // Build the app first (or use pre-built)
    const distPath = path.join(__dirname, "../dist");

    let executablePath: string;
    if (process.platform === "darwin") {
      executablePath = path.join(
        distPath,
        "mac",
        "MyApp.app",
        "Contents",
        "MacOS",
        "MyApp",
      );
    } else if (process.platform === "win32") {
      executablePath = path.join(distPath, "win-unpacked", "MyApp.exe");
    } else {
      executablePath = path.join(distPath, "linux-unpacked", "myapp");
    }

    const electronApp = await electron.launch({ executablePath });
    await use(electronApp);
    await electronApp.close();
  },
});
```

## Anti-Patterns to Avoid

| Anti-Pattern                          | Problem                      | Solution                                     |
| ------------------------------------- | ---------------------------- | -------------------------------------------- |
| Not closing ElectronApplication       | Resource leaks               | Always call `electronApp.close()` in cleanup |
| Hardcoded executable paths            | Breaks cross-platform        | Use platform detection                       |
| Testing packaged app without building | Outdated code                | Build before testing or test dev mode        |
| Ignoring IPC in tests                 | Missing coverage             | Test IPC communication explicitly            |
| Not mocking native dialogs            | Tests hang waiting for input | Mock dialog responses                        |

## Related References

- **Fixtures**: See [fixtures-hooks.md](../core/fixtures-hooks.md) for custom fixture patterns
- **Component Testing**: See [component-testing.md](component-testing.md) for renderer testing patterns
- **Debugging**: See [debugging.md](../debugging/debugging.md) for troubleshooting
