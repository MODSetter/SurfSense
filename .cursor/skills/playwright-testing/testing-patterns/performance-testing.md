# Performance Testing & Web Vitals

## Table of Contents

1. [Core Web Vitals](#core-web-vitals)
2. [Performance Metrics](#performance-metrics)
3. [Performance Budgets](#performance-budgets)
4. [Lighthouse Integration](#lighthouse-integration)
5. [Performance Fixtures](#performance-fixtures)
6. [CI Performance Monitoring](#ci-performance-monitoring)

## Core Web Vitals

### Measure LCP, FID, CLS

```typescript
test("core web vitals within thresholds", async ({ page }) => {
  // Inject web-vitals library
  await page.addInitScript(() => {
    (window as any).__webVitals = {};

    // Simplified web vitals collection
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.entryType === "largest-contentful-paint") {
          (window as any).__webVitals.lcp = entry.startTime;
        }
      }
    }).observe({ type: "largest-contentful-paint", buffered: true });

    new PerformanceObserver((list) => {
      let cls = 0;
      for (const entry of list.getEntries() as any[]) {
        if (!entry.hadRecentInput) {
          cls += entry.value;
        }
      }
      (window as any).__webVitals.cls = cls;
    }).observe({ type: "layout-shift", buffered: true });
  });

  await page.goto("/");

  // Wait for page to stabilize
  await page.waitForLoadState("networkidle");

  // Get metrics
  const vitals = await page.evaluate(() => (window as any).__webVitals);

  // Assert thresholds (Google's "good" thresholds)
  expect(vitals.lcp).toBeLessThan(2500); // LCP < 2.5s
  expect(vitals.cls).toBeLessThan(0.1); // CLS < 0.1
});
```

### Using web-vitals Library

```typescript
test("web vitals with library", async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__vitals = {};
  });

  // Inject web-vitals after navigation
  await page.goto("/");

  await page.addScriptTag({
    url: "https://unpkg.com/web-vitals@3/dist/web-vitals.iife.js",
  });

  await page.evaluate(() => {
    const { onLCP, onFID, onCLS, onFCP, onTTFB } = (window as any).webVitals;

    onLCP((metric: any) => ((window as any).__vitals.lcp = metric.value));
    onFID((metric: any) => ((window as any).__vitals.fid = metric.value));
    onCLS((metric: any) => ((window as any).__vitals.cls = metric.value));
    onFCP((metric: any) => ((window as any).__vitals.fcp = metric.value));
    onTTFB((metric: any) => ((window as any).__vitals.ttfb = metric.value));
  });

  // Trigger FID by clicking
  await page.getByRole("button").first().click();

  // Wait and collect
  await page.waitForTimeout(1000);

  const vitals = await page.evaluate(() => (window as any).__vitals);

  console.log("Web Vitals:", vitals);

  // Assertions
  if (vitals.lcp) expect(vitals.lcp).toBeLessThan(2500);
  if (vitals.fid) expect(vitals.fid).toBeLessThan(100);
  if (vitals.cls) expect(vitals.cls).toBeLessThan(0.1);
});
```

## Performance Metrics

### Navigation Timing

```typescript
test("page load performance", async ({ page }) => {
  await page.goto("/");

  const timing = await page.evaluate(() => {
    const nav = performance.getEntriesByType(
      "navigation",
    )[0] as PerformanceNavigationTiming;

    return {
      // Time to First Byte
      ttfb: nav.responseStart - nav.requestStart,
      // DOM Content Loaded
      domContentLoaded: nav.domContentLoadedEventEnd - nav.startTime,
      // Full page load
      loadComplete: nav.loadEventEnd - nav.startTime,
      // DNS lookup
      dns: nav.domainLookupEnd - nav.domainLookupStart,
      // Connection time
      connection: nav.connectEnd - nav.connectStart,
      // Download time
      download: nav.responseEnd - nav.responseStart,
      // DOM processing
      domProcessing: nav.domComplete - nav.domInteractive,
    };
  });

  console.log("Performance timing:", timing);

  // Assertions
  expect(timing.ttfb).toBeLessThan(600); // TTFB < 600ms
  expect(timing.domContentLoaded).toBeLessThan(2000); // DCL < 2s
  expect(timing.loadComplete).toBeLessThan(4000); // Load < 4s
});
```

### Resource Timing

```typescript
test("resource loading performance", async ({ page }) => {
  await page.goto("/");

  const resources = await page.evaluate(() => {
    return performance.getEntriesByType("resource").map((entry) => ({
      name: entry.name.split("/").pop(),
      type: (entry as PerformanceResourceTiming).initiatorType,
      duration: entry.duration,
      size: (entry as PerformanceResourceTiming).transferSize,
    }));
  });

  // Find slow resources
  const slowResources = resources.filter((r) => r.duration > 1000);

  if (slowResources.length > 0) {
    console.warn("Slow resources:", slowResources);
  }

  // Find large resources
  const largeResources = resources.filter((r) => r.size > 500000); // > 500KB

  expect(largeResources.length).toBe(0);
});
```

### Memory Usage

```typescript
test("memory usage is reasonable", async ({ page }) => {
  await page.goto("/dashboard");

  // Check memory (Chrome only)
  const memory = await page.evaluate(() => {
    if ((performance as any).memory) {
      return {
        usedJSHeapSize: (performance as any).memory.usedJSHeapSize,
        totalJSHeapSize: (performance as any).memory.totalJSHeapSize,
      };
    }
    return null;
  });

  if (memory) {
    const usedMB = memory.usedJSHeapSize / 1024 / 1024;
    console.log(`Memory usage: ${usedMB.toFixed(2)} MB`);

    // Assert reasonable memory usage
    expect(usedMB).toBeLessThan(100); // < 100MB
  }
});
```

## Performance Budgets

### Define Budgets

```typescript
// performance-budgets.ts
export const budgets = {
  homepage: {
    lcp: 2500,
    cls: 0.1,
    fcp: 1800,
    ttfb: 600,
    totalSize: 1500000, // 1.5MB
    jsSize: 500000, // 500KB
    imageCount: 20,
  },
  dashboard: {
    lcp: 3000,
    cls: 0.1,
    fcp: 2000,
    ttfb: 800,
    totalSize: 2000000,
    jsSize: 800000,
  },
};
```

### Test Against Budgets

```typescript
import { budgets } from "./performance-budgets";

test("homepage meets performance budget", async ({ page }) => {
  const budget = budgets.homepage;

  await page.goto("/");
  await page.waitForLoadState("networkidle");

  // Measure LCP
  const lcp = await page.evaluate(() => {
    return new Promise<number>((resolve) => {
      new PerformanceObserver((list) => {
        const entries = list.getEntries();
        resolve(entries[entries.length - 1].startTime);
      }).observe({ type: "largest-contentful-paint", buffered: true });
    });
  });

  // Measure resources
  const resources = await page.evaluate(() => {
    const entries = performance.getEntriesByType(
      "resource",
    ) as PerformanceResourceTiming[];
    return {
      totalSize: entries.reduce((sum, e) => sum + (e.transferSize || 0), 0),
      jsSize: entries
        .filter((e) => e.initiatorType === "script")
        .reduce((sum, e) => sum + (e.transferSize || 0), 0),
      imageCount: entries.filter((e) => e.initiatorType === "img").length,
    };
  });

  // Assert budgets
  expect(lcp, "LCP exceeds budget").toBeLessThan(budget.lcp);
  expect(resources.totalSize, "Total size exceeds budget").toBeLessThan(
    budget.totalSize,
  );
  expect(resources.jsSize, "JS size exceeds budget").toBeLessThan(
    budget.jsSize,
  );
  expect(resources.imageCount, "Too many images").toBeLessThanOrEqual(
    budget.imageCount,
  );
});
```

### Budget Fixture

```typescript
// fixtures/performance.fixture.ts
type PerformanceBudget = {
  lcp?: number;
  cls?: number;
  ttfb?: number;
  totalSize?: number;
};

type PerformanceFixtures = {
  assertBudget: (budget: PerformanceBudget) => Promise<void>;
};

export const test = base.extend<PerformanceFixtures>({
  assertBudget: async ({ page }, use) => {
    await use(async (budget) => {
      const metrics = await page.evaluate(() => {
        const nav = performance.getEntriesByType(
          "navigation",
        )[0] as PerformanceNavigationTiming;
        const resources = performance.getEntriesByType(
          "resource",
        ) as PerformanceResourceTiming[];

        return {
          ttfb: nav.responseStart - nav.requestStart,
          totalSize: resources.reduce(
            (sum, r) => sum + (r.transferSize || 0),
            0,
          ),
        };
      });

      if (budget.ttfb) {
        expect(
          metrics.ttfb,
          `TTFB ${metrics.ttfb}ms exceeds budget ${budget.ttfb}ms`,
        ).toBeLessThan(budget.ttfb);
      }

      if (budget.totalSize) {
        expect(metrics.totalSize, `Total size exceeds budget`).toBeLessThan(
          budget.totalSize,
        );
      }
    });
  },
});
```

## Lighthouse Integration

### Using playwright-lighthouse

```bash
npm install -D playwright-lighthouse lighthouse
```

```typescript
import { playAudit } from "playwright-lighthouse";

test("lighthouse audit", async ({ page }) => {
  await page.goto("/");

  // Run Lighthouse
  const audit = await playAudit({
    page,
    port: 9222, // Chrome debugging port
    thresholds: {
      performance: 80,
      accessibility: 90,
      "best-practices": 80,
      seo: 80,
    },
  });

  // Assertions
  expect(audit.lhr.categories.performance.score * 100).toBeGreaterThanOrEqual(
    80,
  );
  expect(audit.lhr.categories.accessibility.score * 100).toBeGreaterThanOrEqual(
    90,
  );
});
```

### Lighthouse with Config

```typescript
test("lighthouse with custom config", async ({ page }, testInfo) => {
  await page.goto("/");

  const audit = await playAudit({
    page,
    port: 9222,
    thresholds: {
      performance: 70,
    },
    config: {
      extends: "lighthouse:default",
      settings: {
        onlyCategories: ["performance"],
        throttling: {
          rttMs: 40,
          throughputKbps: 10240,
          cpuSlowdownMultiplier: 1,
        },
      },
    },
  });

  // Save report
  const reportPath = testInfo.outputPath("lighthouse-report.html");
  // Save audit.report to file

  // Attach to test report
  await testInfo.attach("lighthouse", {
    body: JSON.stringify(audit.lhr),
    contentType: "application/json",
  });
});
```

## CI Performance Monitoring

### Track Performance Over Time

```typescript
// reporters/perf-reporter.ts
import { Reporter, TestResult } from "@playwright/test/reporter";

class PerfReporter implements Reporter {
  private metrics: any[] = [];

  onTestEnd(test: any, result: TestResult) {
    const perfAnnotation = test.annotations.find(
      (a: any) => a.type === "performance",
    );

    if (perfAnnotation) {
      this.metrics.push({
        test: test.title,
        ...JSON.parse(perfAnnotation.description),
        timestamp: new Date().toISOString(),
      });
    }
  }

  async onEnd() {
    // Send to metrics service
    if (process.env.METRICS_ENDPOINT) {
      await fetch(process.env.METRICS_ENDPOINT, {
        method: "POST",
        body: JSON.stringify({
          commit: process.env.GITHUB_SHA,
          branch: process.env.GITHUB_REF,
          metrics: this.metrics,
        }),
      });
    }
  }
}

export default PerfReporter;
```

### Performance Regression Detection

```typescript
test("no performance regression", async ({ page }) => {
  await page.goto("/");

  const metrics = await page.evaluate(() => {
    const nav = performance.getEntriesByType(
      "navigation",
    )[0] as PerformanceNavigationTiming;
    return {
      loadTime: nav.loadEventEnd - nav.startTime,
    };
  });

  // Compare against baseline (could be from file or API)
  const baseline = 2000; // ms
  const threshold = 1.1; // 10% regression allowed

  expect(
    metrics.loadTime,
    `Load time ${metrics.loadTime}ms is ${((metrics.loadTime / baseline - 1) * 100).toFixed(1)}% slower than baseline`,
  ).toBeLessThan(baseline * threshold);
});
```

## Anti-Patterns to Avoid

| Anti-Pattern                | Problem                   | Solution                         |
| --------------------------- | ------------------------- | -------------------------------- |
| Testing only once           | Results vary              | Run multiple times, use averages |
| Ignoring network conditions | Unrealistic results       | Test with throttling             |
| No baseline comparison      | Can't detect regressions  | Track metrics over time          |
| Testing in dev mode         | Slow, not production-like | Test production builds           |

## Related References

- **Performance Optimization**: See [performance.md](../infrastructure-ci-cd/performance.md) for test execution performance
- **CI/CD**: See [ci-cd.md](../infrastructure-ci-cd/ci-cd.md) for CI integration
