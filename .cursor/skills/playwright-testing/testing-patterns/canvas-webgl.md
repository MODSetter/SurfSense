# Canvas & WebGL Testing

## Table of Contents

1. [Canvas Basics](#canvas-basics)
2. [Visual Comparison](#visual-comparison)
3. [Interaction Testing](#interaction-testing)
4. [WebGL Testing](#webgl-testing)
5. [Chart Libraries](#chart-libraries)
6. [Game & Animation Testing](#game--animation-testing)

## Canvas Basics

### Locating Canvas Elements

```typescript
test("find canvas", async ({ page }) => {
  await page.goto("/canvas-app");

  // By tag
  const canvas = page.locator("canvas");

  // By ID or class
  const gameCanvas = page.locator("canvas#game");
  const chartCanvas = page.locator("canvas.chart-canvas");

  // Verify canvas is present and visible
  await expect(canvas).toBeVisible();

  // Get canvas dimensions
  const box = await canvas.boundingBox();
  console.log(`Canvas size: ${box?.width}x${box?.height}`);
});
```

### Canvas Screenshot Testing

```typescript
test("canvas renders correctly", async ({ page }) => {
  await page.goto("/chart");

  // Wait for canvas to be ready (check for specific content)
  await page.waitForFunction(() => {
    const canvas = document.querySelector("canvas");
    const ctx = canvas?.getContext("2d");
    // Check if canvas has been drawn to
    return ctx && !isCanvasBlank(canvas);

    function isCanvasBlank(canvas) {
      const ctx = canvas.getContext("2d");
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      return !data.some((channel) => channel !== 0);
    }
  });

  // Screenshot just the canvas
  const canvas = page.locator("canvas");
  await expect(canvas).toHaveScreenshot("chart.png");
});
```

### Extracting Canvas Data

```typescript
test("verify canvas content", async ({ page }) => {
  await page.goto("/drawing-app");

  // Get canvas image data
  const imageData = await page.evaluate(() => {
    const canvas = document.querySelector("canvas") as HTMLCanvasElement;
    return canvas.toDataURL("image/png");
  });

  // Verify it's not empty
  expect(imageData).toMatch(/^data:image\/png;base64,.+/);

  // Get pixel data at specific location
  const pixelColor = await page.evaluate(() => {
    const canvas = document.querySelector("canvas") as HTMLCanvasElement;
    const ctx = canvas.getContext("2d")!;
    const pixel = ctx.getImageData(100, 100, 1, 1).data;
    return { r: pixel[0], g: pixel[1], b: pixel[2], a: pixel[3] };
  });

  // Verify specific pixel color
  expect(pixelColor.r).toBeGreaterThan(200); // Expecting red-ish
});
```

## Visual Comparison

### Screenshot Assertions

```typescript
test("chart matches baseline", async ({ page }) => {
  await page.goto("/dashboard");

  // Wait for chart animation to complete
  await page.waitForTimeout(1000); // Or better: wait for specific state

  // Full page screenshot
  await expect(page).toHaveScreenshot("dashboard.png", {
    maxDiffPixels: 100, // Allow small differences
  });

  // Just the canvas
  const chart = page.locator("canvas#sales-chart");
  await expect(chart).toHaveScreenshot("sales-chart.png", {
    maxDiffPixelRatio: 0.01, // 1% difference allowed
  });
});
```

### Handling Animation

```typescript
test("animated canvas", async ({ page }) => {
  await page.goto("/animated-chart");

  // Pause animation before screenshot
  await page.evaluate(() => {
    // Common pattern: chart libraries expose pause method
    window.chartInstance?.stop?.();

    // Or override requestAnimationFrame
    window.requestAnimationFrame = () => 0;
  });

  await expect(page.locator("canvas")).toHaveScreenshot();
});

test("wait for animation complete", async ({ page }) => {
  await page.goto("/chart-with-animation");

  // Wait for animation complete event
  await page.evaluate(() => {
    return new Promise<void>((resolve) => {
      if (window.chart?.isAnimating === false) {
        resolve();
      } else {
        window.chart?.on("animationComplete", resolve);
      }
    });
  });

  await expect(page.locator("canvas")).toHaveScreenshot();
});
```

### Threshold Configuration

```typescript
// playwright.config.ts
export default defineConfig({
  expect: {
    toHaveScreenshot: {
      // Increased threshold for canvas (anti-aliasing differences)
      maxDiffPixelRatio: 0.02,
      threshold: 0.3, // Per-pixel color threshold
      animations: "disabled",
    },
  },
});
```

## Interaction Testing

### Click on Canvas

```typescript
test("click on canvas element", async ({ page }) => {
  await page.goto("/interactive-map");

  const canvas = page.locator("canvas");

  // Click at specific coordinates
  await canvas.click({ position: { x: 150, y: 200 } });

  // Verify click was registered
  await expect(page.locator("#info-panel")).toContainText("Location: Paris");
});
```

### Drawing on Canvas

```typescript
test("draw on canvas", async ({ page }) => {
  await page.goto("/whiteboard");

  const canvas = page.locator("canvas");
  const box = await canvas.boundingBox();

  // Draw a line using mouse
  await page.mouse.move(box!.x + 50, box!.y + 50);
  await page.mouse.down();
  await page.mouse.move(box!.x + 200, box!.y + 200, { steps: 10 });
  await page.mouse.up();

  // Verify something was drawn
  const hasDrawing = await page.evaluate(() => {
    const canvas = document.querySelector("canvas") as HTMLCanvasElement;
    const ctx = canvas.getContext("2d")!;
    const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    return data.some((v, i) => i % 4 !== 3 && v !== 255); // Non-white pixels
  });

  expect(hasDrawing).toBe(true);
});
```

### Drag and Drop

```typescript
test("drag canvas element", async ({ page }) => {
  await page.goto("/diagram-editor");

  const canvas = page.locator("canvas");
  const box = await canvas.boundingBox();

  // Drag shape from position A to B
  await page.mouse.move(box!.x + 100, box!.y + 100);
  await page.mouse.down();
  await page.mouse.move(box!.x + 300, box!.y + 200, { steps: 20 });
  await page.mouse.up();

  // Verify via screenshot or state check
  await expect(canvas).toHaveScreenshot("shape-moved.png");
});
```

### Touch Gestures on Canvas

```typescript
test("pinch zoom on canvas", async ({ page }) => {
  await page.goto("/map");

  const canvas = page.locator("canvas");
  const box = await canvas.boundingBox();
  const centerX = box!.x + box!.width / 2;
  const centerY = box!.y + box!.height / 2;

  // Simulate pinch zoom using two touch points
  await page.touchscreen.tap(centerX, centerY);

  // Use evaluate for complex gestures
  await page.evaluate(
    async ({ x, y }) => {
      const target = document.querySelector("canvas")!;

      // Simulate pinch start
      const touch1 = new Touch({
        identifier: 1,
        target,
        clientX: x - 50,
        clientY: y,
      });
      const touch2 = new Touch({
        identifier: 2,
        target,
        clientX: x + 50,
        clientY: y,
      });

      target.dispatchEvent(
        new TouchEvent("touchstart", {
          touches: [touch1, touch2],
          targetTouches: [touch1, touch2],
          bubbles: true,
        }),
      );

      // Simulate pinch out
      const touch1End = new Touch({
        identifier: 1,
        target,
        clientX: x - 100,
        clientY: y,
      });
      const touch2End = new Touch({
        identifier: 2,
        target,
        clientX: x + 100,
        clientY: y,
      });

      target.dispatchEvent(
        new TouchEvent("touchmove", {
          touches: [touch1End, touch2End],
          targetTouches: [touch1End, touch2End],
          bubbles: true,
        }),
      );

      target.dispatchEvent(new TouchEvent("touchend", { bubbles: true }));
    },
    { x: centerX, y: centerY },
  );

  // Verify zoom level changed
  const zoomLevel = await page.locator("#zoom-indicator").textContent();
  expect(parseFloat(zoomLevel!)).toBeGreaterThan(1);
});
```

## WebGL Testing

### Checking WebGL Support

```typescript
test("WebGL is supported", async ({ page }) => {
  await page.goto("/3d-viewer");

  const hasWebGL = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    const gl =
      canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    return !!gl;
  });

  expect(hasWebGL).toBe(true);
});
```

### WebGL Screenshot Testing

```typescript
test("3D scene renders", async ({ page }) => {
  await page.goto("/3d-model-viewer");

  // Wait for WebGL scene to render
  await page.waitForFunction(() => {
    const canvas = document.querySelector("canvas");
    if (!canvas) return false;

    const gl = canvas.getContext("webgl") || canvas.getContext("webgl2");
    if (!gl) return false;

    // Check if something has been drawn
    const pixels = new Uint8Array(4);
    gl.readPixels(
      canvas.width / 2,
      canvas.height / 2,
      1,
      1,
      gl.RGBA,
      gl.UNSIGNED_BYTE,
      pixels,
    );
    return pixels.some((p) => p > 0);
  });

  // Screenshot comparison (higher threshold for WebGL)
  await expect(page.locator("canvas")).toHaveScreenshot("3d-scene.png", {
    maxDiffPixelRatio: 0.05, // WebGL can have more variation
  });
});
```

### Testing Three.js Applications

```typescript
test("Three.js scene interaction", async ({ page }) => {
  await page.goto("/three-demo");

  // Wait for scene to be ready
  await page.waitForFunction(() => window.scene?.children?.length > 0);

  // Interact with scene (orbit controls)
  const canvas = page.locator("canvas");
  const box = await canvas.boundingBox();

  // Rotate camera by dragging
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    box!.x + box!.width / 2 + 100,
    box!.y + box!.height / 2,
    {
      steps: 10,
    },
  );
  await page.mouse.up();

  // Verify camera position changed
  const cameraRotation = await page.evaluate(() => {
    return window.camera?.rotation?.y;
  });

  expect(cameraRotation).not.toBe(0);
});
```

## Chart Libraries

### Chart.js Testing

```typescript
test("Chart.js renders data", async ({ page }) => {
  await page.goto("/chartjs-demo");

  // Wait for Chart.js to initialize
  await page.waitForFunction(() => {
    return window.Chart && document.querySelector("canvas")?.__chart__;
  });

  // Get chart data via Chart.js API
  const chartData = await page.evaluate(() => {
    const canvas = document.querySelector("canvas") as any;
    const chart = canvas.__chart__;
    return chart.data.datasets[0].data;
  });

  expect(chartData).toEqual([12, 19, 3, 5, 2, 3]);

  // Screenshot test
  await expect(page.locator("canvas")).toHaveScreenshot();
});
```

### D3.js / ECharts Testing

```typescript
test("chart library interaction", async ({ page }) => {
  await page.goto("/chart-demo");

  // Wait for chart to render
  await page.waitForFunction(() => document.querySelector("canvas, svg.chart"));

  // For SVG charts (D3)
  const bars = page.locator("svg.chart rect.bar");
  if ((await bars.count()) > 0) {
    await bars.first().hover();
    await expect(page.locator(".tooltip")).toBeVisible();
  }

  // For canvas charts (ECharts, Chart.js)
  const canvas = page.locator("canvas");
  await canvas.click({ position: { x: 200, y: 150 } });
});
```

## Game & Animation Testing

### Frame-by-Frame Testing

```typescript
test("game frame control", async ({ page }) => {
  await page.goto("/game");

  // Pause and step through frames
  await page.evaluate(() => window.gameLoop?.pause());
  await page.evaluate(() => window.gameLoop?.tick());
  await expect(page.locator("canvas")).toHaveScreenshot("frame-1.png");

  for (let i = 0; i < 10; i++) {
    await page.evaluate(() => window.gameLoop?.tick());
  }
  await expect(page.locator("canvas")).toHaveScreenshot("frame-11.png");
});
```

### Testing Game State

```typescript
test("game state changes", async ({ page }) => {
  await page.goto("/game");

  const initialScore = await page.evaluate(() => window.game?.score);
  expect(initialScore).toBe(0);

  await page.keyboard.press("Space"); // Action
  await page.waitForTimeout(500);

  const newScore = await page.evaluate(() => window.game?.score);
  expect(newScore).toBeGreaterThan(0);
});
```

## Anti-Patterns to Avoid

| Anti-Pattern             | Problem                  | Solution                            |
| ------------------------ | ------------------------ | ----------------------------------- |
| Pixel-perfect assertions | Fails across browsers/OS | Use maxDiffPixelRatio threshold     |
| Not waiting for render   | Blank canvas screenshots | Wait for draw completion            |
| Testing raw pixel data   | Brittle and slow         | Use visual comparison               |
| Ignoring animation       | Flaky screenshots        | Pause/disable animations            |
| Hardcoded coordinates    | Breaks on resize         | Calculate relative to canvas bounds |

## Related References

- **Visual Testing**: See [test-suite-structure.md](../core/test-suite-structure.md) for visual regression setup
- **Mobile Gestures**: See [mobile-testing.md](../advanced/mobile-testing.md) for touch interactions
- **Performance**: See [performance-testing.md](performance-testing.md) for FPS monitoring
