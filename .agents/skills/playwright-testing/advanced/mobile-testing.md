# Mobile & Responsive Testing

## Table of Contents

1. [Device Emulation](#device-emulation)
2. [Touch Gestures](#touch-gestures)
3. [Viewport Testing](#viewport-testing)
4. [Mobile-Specific UI](#mobile-specific-ui)
5. [Responsive Breakpoints](#responsive-breakpoints)

## Device Emulation

### Use Built-in Devices

```typescript
import { test, devices } from "@playwright/test";

// Configure in playwright.config.ts
export default defineConfig({
  projects: [
    { name: "Desktop Chrome", use: { ...devices["Desktop Chrome"] } },
    { name: "Mobile Safari", use: { ...devices["iPhone 14"] } },
    { name: "Mobile Chrome", use: { ...devices["Pixel 7"] } },
    { name: "Tablet", use: { ...devices["iPad Pro 11"] } },
  ],
});
```

### Custom Device Configuration

```typescript
test.use({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 3,
  isMobile: true,
  hasTouch: true,
  userAgent:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
});

test("custom mobile device", async ({ page }) => {
  await page.goto("/");
  // Test runs with custom device settings
});
```

### Test Across Multiple Devices

```typescript
const mobileDevices = ["iPhone 14", "Pixel 7", "Galaxy S21"];

for (const deviceName of mobileDevices) {
  test(`checkout on ${deviceName}`, async ({ browser }) => {
    const device = devices[deviceName];
    const context = await browser.newContext({ ...device });
    const page = await context.newPage();

    await page.goto("/checkout");
    await expect(page.getByRole("button", { name: "Pay" })).toBeVisible();

    await context.close();
  });
}
```

## Touch Gestures

### Tap

```typescript
test.use({ hasTouch: true });

test("tap to interact", async ({ page }) => {
  await page.goto("/gallery");

  // Tap is like click but for touch devices
  await page.getByRole("img", { name: "Photo 1" }).tap();

  await expect(page.getByRole("dialog")).toBeVisible();
});
```

### Swipe

```typescript
test("swipe carousel", async ({ page }) => {
  await page.goto("/carousel");

  const carousel = page.getByTestId("carousel");
  const box = await carousel.boundingBox();

  if (box) {
    // Swipe left
    await page.touchscreen.tap(box.x + box.width - 50, box.y + box.height / 2);
    await page.mouse.move(box.x + 50, box.y + box.height / 2);

    // Or use drag
    await carousel.dragTo(carousel, {
      sourcePosition: { x: box.width - 50, y: box.height / 2 },
      targetPosition: { x: 50, y: box.height / 2 },
    });
  }

  await expect(page.getByText("Slide 2")).toBeVisible();
});
```

### Swipe Fixture

```typescript
// fixtures/touch.fixture.ts
import { test as base, Page } from "@playwright/test";

type TouchFixtures = {
  swipe: (
    element: Locator,
    direction: "left" | "right" | "up" | "down",
  ) => Promise<void>;
};

export const test = base.extend<TouchFixtures>({
  swipe: async ({ page }, use) => {
    await use(async (element, direction) => {
      const box = await element.boundingBox();
      if (!box) throw new Error("Element not visible");

      const centerX = box.x + box.width / 2;
      const centerY = box.y + box.height / 2;
      const distance = 100;

      const moves = {
        left: {
          startX: centerX + distance,
          endX: centerX - distance,
          y: centerY,
        },
        right: {
          startX: centerX - distance,
          endX: centerX + distance,
          y: centerY,
        },
        up: {
          startX: centerX,
          endX: centerX,
          startY: centerY + distance,
          endY: centerY - distance,
        },
        down: {
          startX: centerX,
          endX: centerX,
          startY: centerY - distance,
          endY: centerY + distance,
        },
      };

      const move = moves[direction];
      await page.touchscreen.tap(move.startX, move.startY ?? move.y);
      await page.mouse.move(move.endX, move.endY ?? move.y, { steps: 10 });
      await page.mouse.up();
    });
  },
});

// Usage
test("swipe to delete", async ({ page, swipe }) => {
  await page.goto("/inbox");

  const message = page.getByTestId("message-1");
  await swipe(message, "left");

  await expect(page.getByRole("button", { name: "Delete" })).toBeVisible();
});
```

### Long Press

```typescript
test("long press for context menu", async ({ page }) => {
  await page.goto("/files");

  const file = page.getByText("document.pdf");
  const box = await file.boundingBox();

  if (box) {
    // Touch down
    await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);

    // Hold for 500ms
    await page.waitForTimeout(500);

    // Context menu should appear
    await expect(page.getByRole("menu")).toBeVisible();
  }
});
```

### Pinch Zoom

```typescript
test("pinch to zoom image", async ({ page }) => {
  await page.goto("/map");

  // Pinch zoom requires two touch points
  // Playwright doesn't have native pinch support, so we simulate via evaluate
  await page.evaluate(() => {
    const element = document.querySelector("#map");
    if (element) {
      // Simulate wheel event as fallback for zoom
      element.dispatchEvent(
        new WheelEvent("wheel", {
          deltaY: -100, // Negative = zoom in
          ctrlKey: true, // Ctrl+wheel = pinch on many apps
        }),
      );
    }
  });

  // Or trigger the app's zoom function directly
  await page.evaluate(() => {
    (window as any).mapInstance?.setZoom(15);
  });
});
```

## Viewport Testing

### Test Different Sizes

```typescript
const viewports = [
  { name: "mobile", width: 375, height: 667 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "desktop", width: 1920, height: 1080 },
];

for (const { name, width, height } of viewports) {
  test(`navigation on ${name}`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await page.goto("/");

    if (width < 768) {
      // Mobile: should have hamburger menu
      await expect(page.getByRole("button", { name: "Menu" })).toBeVisible();
    } else {
      // Desktop: should have visible nav links
      await expect(page.getByRole("link", { name: "Products" })).toBeVisible();
    }
  });
}
```

### Dynamic Viewport Changes

```typescript
test("responsive layout change", async ({ page }) => {
  await page.setViewportSize({ width: 1200, height: 800 });
  await page.goto("/dashboard");

  // Desktop: sidebar visible
  await expect(page.getByRole("complementary")).toBeVisible();

  // Resize to mobile
  await page.setViewportSize({ width: 375, height: 667 });

  // Mobile: sidebar hidden, hamburger visible
  await expect(page.getByRole("complementary")).toBeHidden();
  await expect(page.getByRole("button", { name: "Menu" })).toBeVisible();
});
```

## Mobile-Specific UI

### Hamburger Menu

```typescript
test("mobile navigation", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto("/");

  // Open hamburger menu
  await page.getByRole("button", { name: "Menu" }).click();

  // Navigation drawer should appear
  const nav = page.getByRole("navigation");
  await expect(nav).toBeVisible();

  // Navigate via mobile menu
  await nav.getByRole("link", { name: "Products" }).click();

  await expect(page).toHaveURL("/products");
  // Menu should close after navigation
  await expect(nav).toBeHidden();
});
```

### Bottom Sheet

```typescript
test("bottom sheet interaction", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto("/product/123");

  await page.getByRole("button", { name: "Add to Cart" }).click();

  // Bottom sheet appears
  const sheet = page.getByRole("dialog");
  await expect(sheet).toBeVisible();

  // Select options
  await sheet.getByRole("combobox", { name: "Size" }).selectOption("Large");
  await sheet.getByRole("button", { name: "Confirm" }).click();

  await expect(page.getByText("Added to cart")).toBeVisible();
});
```

### Pull to Refresh

```typescript
test("pull to refresh", async ({ page }) => {
  await page.goto("/feed");

  const feed = page.getByTestId("feed");
  const initialFirstItem = await feed.locator("> *").first().textContent();

  // Simulate pull down
  const box = await feed.boundingBox();
  if (box) {
    await page.touchscreen.tap(box.x + box.width / 2, box.y + 50);
    await page.mouse.move(box.x + box.width / 2, box.y + 200, { steps: 20 });
    await page.mouse.up();
  }

  // Wait for refresh
  await expect(page.getByTestId("loading")).toBeVisible();
  await expect(page.getByTestId("loading")).toBeHidden();

  // Content should be updated (in a real app)
});
```

## Responsive Breakpoints

### Test All Breakpoints

```typescript
const breakpoints = {
  xs: 320,
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  "2xl": 1536,
};

test.describe("responsive header", () => {
  for (const [name, width] of Object.entries(breakpoints)) {
    test(`header at ${name} (${width}px)`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await page.goto("/");

      if (width < 768) {
        await expect(page.getByTestId("mobile-menu-button")).toBeVisible();
        await expect(page.getByTestId("desktop-nav")).toBeHidden();
      } else {
        await expect(page.getByTestId("mobile-menu-button")).toBeHidden();
        await expect(page.getByTestId("desktop-nav")).toBeVisible();
      }
    });
  }
});
```

### Visual Regression at Breakpoints

```typescript
test.describe("visual regression", () => {
  const sizes = [
    { width: 375, height: 667, name: "mobile" },
    { width: 768, height: 1024, name: "tablet" },
    { width: 1440, height: 900, name: "desktop" },
  ];

  for (const { width, height, name } of sizes) {
    test(`homepage at ${name}`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await page.goto("/");

      await expect(page).toHaveScreenshot(`homepage-${name}.png`);
    });
  }
});
```

## Anti-Patterns to Avoid

| Anti-Pattern                | Problem                   | Solution                         |
| --------------------------- | ------------------------- | -------------------------------- |
| Only testing one viewport   | Misses responsive bugs    | Test multiple breakpoints        |
| Ignoring touch events       | Features broken on mobile | Test tap, swipe, long press      |
| Hardcoded viewport in tests | Can't test multiple sizes | Use `page.setViewportSize()`     |
| Not testing orientation     | Landscape bugs missed     | Test both portrait and landscape |

## Related References

- **Visual Testing**: See [test-suite-structure.md](../core/test-suite-structure.md) for screenshot testing
- **Locators**: See [locators.md](../core/locators.md) for mobile-friendly selectors
- **Browser APIs**: See [browser-apis.md](../browser-apis/browser-apis.md) for permissions (camera, geolocation, notifications)
- **Canvas/Touch**: See [canvas-webgl.md](../testing-patterns/canvas-webgl.md) for touch gestures on canvas elements
