# Visual Regression Testing

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Patterns](#patterns)
3. [Decision Guide](#decision-guide)
4. [Anti-Patterns](#anti-patterns)
5. [Troubleshooting](#troubleshooting)

> **When to use**: Detecting unintended visual changes—layout shifts, style regressions, broken responsive designs—that functional assertions miss.

## Quick Reference

```typescript
// Element screenshot
await expect(page.getByTestId('product-card')).toHaveScreenshot();

// Full page screenshot
await expect(page).toHaveScreenshot('landing-hero.png');

// Threshold for minor pixel variance
await expect(page).toHaveScreenshot({ maxDiffPixelRatio: 0.01 });

// Mask volatile content
await expect(page).toHaveScreenshot({
  mask: [page.getByTestId('clock'), page.getByRole('img', { name: 'User photo' })],
});

// Disable CSS animations
await expect(page).toHaveScreenshot({ animations: 'disabled' });

// Update baselines
npx playwright test --update-snapshots
```

## Patterns

### Masking Volatile Content

**Use when**: Page contains timestamps, avatars, ad slots, relative dates, random images, or A/B variants.

The `mask` option overlays a solid box over specified locators before capturing.

```typescript
test('analytics panel with masked dynamic elements', async ({ page }) => {
  await page.goto('/analytics');

  await expect(page).toHaveScreenshot('analytics.png', {
    mask: [
      page.getByTestId('last-updated'),
      page.getByTestId('profile-avatar'),
      page.getByTestId('active-users'),
      page.locator('.promo-banner'),
    ],
    maskColor: '#FF00FF',
  });
});

test('activity stream with relative times', async ({ page }) => {
  await page.goto('/activity');

  await expect(page).toHaveScreenshot('activity.png', {
    mask: [page.locator('time[datetime]')],
  });
});
```

**Alternative: freeze content with JavaScript** when masking affects layout:

```typescript
test('freeze timestamps before capture', async ({ page }) => {
  await page.goto('/analytics');

  await page.evaluate(() => {
    document.querySelectorAll('[data-testid="time-display"]').forEach((el) => {
      el.textContent = 'Jan 1, 2025 12:00 PM';
    });
  });

  await expect(page).toHaveScreenshot('analytics-frozen.png');
});
```

### Disabling Animations

**Use when**: Always. CSS animations and transitions are the primary cause of flaky visual diffs.

```typescript
test('renders without animation interference', async ({ page }) => {
  await page.goto('/');

  await expect(page).toHaveScreenshot('home.png', {
    animations: 'disabled',
  });
});
```

**Set globally** in config:

```typescript
// playwright.config.ts
export default defineConfig({
  expect: {
    toHaveScreenshot: {
      animations: 'disabled',
    },
  },
});
```

When `animations: 'disabled'` is set, Playwright injects CSS forcing animation/transition duration to 0s, waits for running animations to finish, then captures.

For JavaScript-driven animations (GSAP, Framer Motion), wait for stability:

```typescript
test('page with JS animations', async ({ page }) => {
  await page.goto('/animated-hero');

  const heroBanner = page.getByTestId('hero-banner');
  await heroBanner.waitFor({ state: 'visible' });
  
  // Wait for animation to complete by checking for stable state
  await expect(heroBanner).not.toHaveClass(/animating/);

  await expect(page).toHaveScreenshot('hero.png', {
    animations: 'disabled',
  });
});
```

### Configuring Thresholds

**Use when**: Minor rendering differences from anti-aliasing, font hinting, or sub-pixel rendering cause false failures.

| Option | Controls | Typical Value |
|---|---|---|
| `maxDiffPixels` | Absolute pixel count that can differ | `100` for pages, `10` for components |
| `maxDiffPixelRatio` | Fraction of total pixels (0-1) | `0.01` (1%) for pages |
| `threshold` | Per-pixel color tolerance (0-1) | `0.2` for most UIs, `0.1` for design systems |

```typescript
test('control panel allows minor variance', async ({ page }) => {
  await page.goto('/control-panel');

  await expect(page).toHaveScreenshot('control-panel.png', {
    maxDiffPixelRatio: 0.01,
  });
});

test('brand logo renders pixel-perfect', async ({ page }) => {
  await page.goto('/brand');

  await expect(page.getByTestId('brand-logo')).toHaveScreenshot('brand-logo.png', {
    maxDiffPixels: 0,
    threshold: 0,
  });
});

test('graph allows anti-aliasing differences', async ({ page }) => {
  await page.goto('/reports');

  await expect(page.getByTestId('sales-graph')).toHaveScreenshot('sales-graph.png', {
    threshold: 0.3,
    maxDiffPixels: 200,
  });
});
```

**Global thresholds** in config:

```typescript
// playwright.config.ts
export default defineConfig({
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
      threshold: 0.2,
      animations: 'disabled',
    },
  },
});
```

### CI Configuration

**Use when**: Running visual tests in CI. Consistent rendering is critical—the same test must produce identical screenshots every time.

**The problem**: Font rendering and anti-aliasing differ across operating systems. macOS snapshots won't match Linux.

**The solution**: Run visual tests in Docker using the official Playwright container. Generate and update snapshots from the same container.

**GitHub Actions with Docker**

```yaml
# .github/workflows/visual-tests.yml
name: Visual Regression Tests
on: [push, pull_request]

jobs:
  visual-tests:
    runs-on: ubuntu-latest
    container:
      image: mcr.microsoft.com/playwright:v1.48.0-noble
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: lts/*
          cache: npm

      - run: npm ci

      - name: Run visual tests
        run: npx playwright test --project=visual
        env:
          HOME: /root

      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: visual-test-report
          path: playwright-report/
          retention-days: 14
```

**Updating snapshots locally using Docker**:

```bash
docker run --rm -v $(pwd):/work -w /work \
  mcr.microsoft.com/playwright:v1.48.0-noble \
  npx playwright test --update-snapshots --project=visual
```

**Add script to `package.json`**:

```json
{
  "scripts": {
    "test:visual": "npx playwright test --project=visual",
    "test:visual:update": "docker run --rm -v $(pwd):/work -w /work mcr.microsoft.com/playwright:v1.48.0-noble npx playwright test --update-snapshots --project=visual"
  }
}
```

**Platform-agnostic snapshots** (requires Docker for generation):

```typescript
// playwright.config.ts
export default defineConfig({
  snapshotPathTemplate: '{testDir}/{testFileDir}/{testFileName}-snapshots/{arg}{-projectName}{ext}',
  projects: [
    {
      name: 'visual',
      testMatch: '**/*.visual.spec.ts',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
```

### Full Page vs Element Screenshots

**Use when**: Deciding scope. Full page catches layout shifts. Element screenshots isolate components and are more stable.

```typescript
test('full page captures layout shifts', async ({ page }) => {
  await page.goto('/');

  // Visible viewport
  await expect(page).toHaveScreenshot('home-viewport.png');

  // Entire scrollable page
  await expect(page).toHaveScreenshot('home-full.png', {
    fullPage: true,
  });
});

test('element screenshot isolates component', async ({ page }) => {
  await page.goto('/catalog');

  await expect(page.getByRole('table')).toHaveScreenshot('catalog-table.png');
  await expect(page.getByTestId('featured-item')).toHaveScreenshot('featured-item.png');
});
```

**Rule of thumb**: Element screenshots for independently changing components. Full page screenshots for key layouts where spacing matters.

### Responsive Visual Testing

**Use when**: Application has responsive breakpoints requiring verification at different viewport sizes.

```typescript
const breakpoints = [
  { name: 'phone', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1440, height: 900 },
];

for (const bp of breakpoints) {
  test(`landing at ${bp.name} (${bp.width}x${bp.height})`, async ({ page }) => {
    await page.setViewportSize({ width: bp.width, height: bp.height });
    await page.goto('/');

    await expect(page).toHaveScreenshot(`landing-${bp.name}.png`, {
      animations: 'disabled',
      fullPage: true,
    });
  });
}
```

**Alternative: use projects for responsive testing**:

```typescript
// playwright.config.ts
export default defineConfig({
  projects: [
    {
      name: 'desktop',
      testMatch: '**/*.visual.spec.ts',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      name: 'tablet',
      testMatch: '**/*.visual.spec.ts',
      use: { ...devices['iPad (gen 7)'] },
    },
    {
      name: 'mobile',
      testMatch: '**/*.visual.spec.ts',
      use: { ...devices['iPhone 14'] },
    },
  ],
});
```

### Component Visual Testing

**Use when**: Testing individual UI components in isolation—buttons, cards, forms, modals. Faster and more stable than full-page screenshots.

```typescript
test.describe('Button visual states', () => {
  test('primary button', async ({ page }) => {
    await page.goto('/storybook/iframe.html?id=button--primary');
    const btn = page.getByRole('button');
    await expect(btn).toHaveScreenshot('btn-primary.png', {
      animations: 'disabled',
    });
  });

  test('primary button hover', async ({ page }) => {
    await page.goto('/storybook/iframe.html?id=button--primary');
    const btn = page.getByRole('button');
    await btn.hover();
    await expect(btn).toHaveScreenshot('btn-primary-hover.png', {
      animations: 'disabled',
    });
  });

  test('button sizes', async ({ page }) => {
    for (const size of ['small', 'medium', 'large']) {
      await page.goto(`/storybook/iframe.html?id=button--${size}`);
      const btn = page.getByRole('button');
      await expect(btn).toHaveScreenshot(`btn-${size}.png`, {
        animations: 'disabled',
      });
    }
  });
});
```

**Using a dedicated test harness** instead of Storybook:

```typescript
test.describe('Card component', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/test-harness/card');
  });

  test('default state', async ({ page }) => {
    await expect(page.getByTestId('card')).toHaveScreenshot('card-default.png', {
      animations: 'disabled',
    });
  });

  test('truncates long content', async ({ page }) => {
    await page.goto('/test-harness/card?content=long');
    await expect(page.getByTestId('card')).toHaveScreenshot('card-long.png', {
      animations: 'disabled',
    });
  });
});
```

### Updating Snapshots

**Use when**: Intentionally changed UI—design refresh, rebrand, new feature. Never update when diff is unexpected.

```bash
# Update all snapshots
npx playwright test --update-snapshots

# Update for specific file
npx playwright test tests/landing.spec.ts --update-snapshots

# Update for specific project
npx playwright test --project=chromium --update-snapshots
```

**Workflow for reviewing changes:**

1. Run tests and view failures in HTML report:
   ```bash
   npx playwright test
   npx playwright show-report
   ```
   The report shows expected, actual, and diff images side-by-side.

2. If changes are intentional, update:
   ```bash
   npx playwright test --update-snapshots
   ```

3. Review updated snapshots before committing:
   ```bash
   git diff --name-only
   ```

**Tag visual tests for selective updates:**

```typescript
test('landing visual @visual', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveScreenshot('landing.png', {
    animations: 'disabled',
  });
});
```

```bash
npx playwright test --grep @visual --update-snapshots
```

### Cross-Browser Visual Testing

**Use when**: Users span Chrome, Firefox, Safari and you need per-browser rendering verification.

Playwright separates snapshots by project name automatically. Each browser gets its own baseline—browsers render fonts and shadows differently.

```typescript
// playwright.config.ts
export default defineConfig({
  expect: {
    toHaveScreenshot: {
      animations: 'disabled',
      maxDiffPixelRatio: 0.01,
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
});
```

**Strategy**: Run visual tests in a single browser (Chromium on Linux in CI) to minimize snapshot count. Add other browsers only when you have actual cross-browser rendering bugs:

```typescript
// playwright.config.ts
export default defineConfig({
  projects: [
    {
      name: 'visual',
      testMatch: '**/*.visual.spec.ts',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'chromium',
      testIgnore: '**/*.visual.spec.ts',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      testIgnore: '**/*.visual.spec.ts',
      use: { ...devices['Desktop Firefox'] },
    },
  ],
});
```

## Decision Guide

| Scenario | Approach | Rationale |
|---|---|---|
| Key landing/marketing pages | Full page, `fullPage: true` | Catches layout shifts, spacing, overall harmony |
| Individual components | Element screenshot | Isolated, fast, immune to unrelated changes |
| Page with dynamic content | Full page + `mask` | Covers layout while ignoring volatile content |
| Design system library | Element per variant, zero threshold | Pixel-perfect enforcement |
| Responsive verification | Screenshot per viewport | Catches breakpoint bugs |
| Cross-browser consistency | Separate snapshots per browser | Browsers render differently |
| CI pipeline | Docker container, Linux-only snapshots | Consistent rendering |
| Threshold: design system | `threshold: 0`, `maxDiffPixels: 0` | Zero tolerance |
| Threshold: content pages | `maxDiffPixelRatio: 0.01`, `threshold: 0.2` | Minor anti-aliasing variance |
| Threshold: charts/graphs | `maxDiffPixels: 200`, `threshold: 0.3` | Anti-aliasing on curves varies |

## Anti-Patterns

| Don't | Problem | Do Instead |
|---|---|---|
| Visual test every page | Massive maintenance, constant false failures | Pick 5-10 key pages and critical components |
| Skip masking dynamic content | Screenshots differ every run, permanently flaky | Use `mask` for all volatile elements |
| Run across macOS, Linux, Windows | Font rendering differs, snapshots never match | Standardize on Linux via Docker |
| Skip Docker in CI | OS updates shift rendering silently | Pin specific Playwright Docker image |
| Blindly run `--update-snapshots` | Accepts unintentional regressions | Always review diff in HTML report first |
| Skip `animations: 'disabled'` | CSS transitions create random diffs | Set globally in config |
| Replace functional assertions with visual tests | Diffs don't tell you *what* broke | Visual tests complement, never replace |
| Commit snapshots from different platforms | Tests fail for everyone | All team members use same Docker container |
| Set threshold too high (`0.1`) | 10% pixel change passes, defeats purpose | Start with `0.01`, adjust per-test |
| Full page on infinite scroll pages | Page height nondeterministic | Element screenshots on above-the-fold content |

## Troubleshooting

### "Screenshot comparison failed" on first CI run after local development

**Cause**: Snapshots generated on macOS locally. CI runs on Linux. Font rendering differs.

**Fix**: Generate snapshots using Docker:

```bash
docker run --rm -v $(pwd):/work -w /work \
  mcr.microsoft.com/playwright:v1.48.0-noble \
  npx playwright test --update-snapshots --project=visual
```

Commit Linux-generated snapshots.

### "Expected screenshot to match but X pixels differ"

**Cause**: Anti-aliasing, font hinting, sub-pixel rendering differences.

**Fix**: Add tolerance:

```typescript
await expect(page).toHaveScreenshot('page.png', {
  maxDiffPixelRatio: 0.01,
  threshold: 0.2,
});
```

Check HTML report diff image to determine if it's regression or noise.

### Visual tests pass locally but fail in CI (even with Docker)

**Cause**: Different Playwright versions locally vs CI.

**Fix**: Ensure `package.json` version matches Docker image tag:

```json
{
  "devDependencies": {
    "@playwright/test": "latest"
  }
}
```

```yaml
container:
  image: mcr.microsoft.com/playwright:v1.48.0-noble
```

### Animations cause random diff failures

**Cause**: CSS animations captured mid-frame.

**Fix**: Set `animations: 'disabled'` globally:

```typescript
// playwright.config.ts
export default defineConfig({
  expect: {
    toHaveScreenshot: {
      animations: 'disabled',
    },
  },
});
```

For JS animations, wait for stable state before capture.

### Snapshot file names conflict between tests

**Cause**: Two tests use same screenshot name without unique paths.

**Fix**: Use explicit unique names:

```typescript
await expect(page).toHaveScreenshot('auth-home.png');
await expect(page).toHaveScreenshot('public-home.png');
```

Or customize snapshot path template:

```typescript
export default defineConfig({
  snapshotPathTemplate: '{testDir}/{testFileDir}/{testFileName}-snapshots/{arg}{-projectName}{ext}',
});
```

### Too many snapshot files to maintain

**Cause**: Visual tests for every page, browser, viewport.

**Fix**: Be selective. Visual test only high-risk pages:
- Landing and marketing pages
- Design system components
- Complex layouts (dashboards, data tables)
- Pages after major refactor

Skip pages where functional assertions cover key elements.
