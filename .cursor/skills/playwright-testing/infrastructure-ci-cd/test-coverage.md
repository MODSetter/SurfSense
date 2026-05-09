# Test Coverage

## Table of Contents

1. [Coverage Setup](#coverage-setup)
2. [Collecting Coverage](#collecting-coverage)
3. [Coverage Reports](#coverage-reports)
4. [Coverage Thresholds](#coverage-thresholds)
5. [Advanced Patterns](#advanced-patterns)
6. [CI Integration](#ci-integration)

## Coverage Setup

### Install Dependencies

```bash
# For V8 coverage (built into Playwright)
# No additional dependencies needed

# For Istanbul-based coverage (more features)
npm install -D nyc @istanbuljs/nyc-config-typescript
```

### Basic Configuration

```typescript
// playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  use: {
    // Enable coverage collection
    contextOptions: {
      // V8 coverage is automatic with the API below
    },
  },
});
```

### V8 Coverage Fixture

```typescript
// fixtures/coverage.ts
import { test as base, expect } from "@playwright/test";
import fs from "fs";
import path from "path";
import { randomUUID } from "crypto";

export const test = base.extend<{}, { collectCoverage: void }>({
  collectCoverage: [
    async ({ browser }, use) => {
      // Start coverage for all pages
      const context = await browser.newContext();
      const page = await context.newPage();

      await page.coverage.startJSCoverage();
      await page.coverage.startCSSCoverage();

      await use();

      // Collect coverage
      const [jsCoverage, cssCoverage] = await Promise.all([
        page.coverage.stopJSCoverage(),
        page.coverage.stopCSSCoverage(),
      ]);

      // Save coverage data
      const coverageDir = "./coverage";
      if (!fs.existsSync(coverageDir)) {
        fs.mkdirSync(coverageDir, { recursive: true });
      }

      fs.writeFileSync(
        path.join(coverageDir, `coverage-${randomUUID()}.json`),
        JSON.stringify([...jsCoverage, ...cssCoverage])
      );

      await context.close();
    },
    { scope: "worker", auto: true },
  ],
});
```

## Collecting Coverage

### Per-Test Coverage

```typescript
test("collect coverage for single test", async ({ page }) => {
  // Start coverage collection
  await page.coverage.startJSCoverage({
    resetOnNavigation: false,
  });

  // Run test
  await page.goto("/app");
  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByText("Success")).toBeVisible();

  // Stop and get coverage
  const coverage = await page.coverage.stopJSCoverage();

  // Filter to only your source files
  const appCoverage = coverage.filter((entry) => entry.url.includes("/src/"));

  console.log(`Covered ${appCoverage.length} source files`);
});
```

### Coverage for Specific Files

```typescript
test("track specific module coverage", async ({ page }) => {
  await page.coverage.startJSCoverage();

  await page.goto("/checkout");
  await page.getByRole("button", { name: "Pay" }).click();

  const coverage = await page.coverage.stopJSCoverage();

  // Find coverage for checkout module
  const checkoutCoverage = coverage.find((c) => c.url.includes("checkout.js"));

  if (checkoutCoverage) {
    const totalBytes = checkoutCoverage.text?.length || 0;
    const coveredBytes = checkoutCoverage.ranges.reduce(
      (sum, range) => sum + (range.end - range.start),
      0
    );
    const percentage = (coveredBytes / totalBytes) * 100;

    console.log(`Checkout module: ${percentage.toFixed(1)}% covered`);
    expect(percentage).toBeGreaterThan(80);
  }
});
```

### CSS Coverage

```typescript
test("collect CSS coverage", async ({ page }) => {
  await page.coverage.startCSSCoverage();

  await page.goto("/app");

  // Interact to trigger different CSS states
  await page.getByRole("button").hover();
  await page.getByRole("dialog").waitFor();

  const cssCoverage = await page.coverage.stopCSSCoverage();

  // Find unused CSS
  for (const entry of cssCoverage) {
    const totalBytes = entry.text?.length || 0;
    const usedBytes = entry.ranges.reduce(
      (sum, range) => sum + (range.end - range.start),
      0
    );
    const unusedPercentage = ((totalBytes - usedBytes) / totalBytes) * 100;

    if (unusedPercentage > 50) {
      console.warn(`${entry.url}: ${unusedPercentage.toFixed(1)}% unused CSS`);
    }
  }
});
```

## Coverage Reports

### Converting to Istanbul Format

```typescript
// scripts/convert-coverage.ts
import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import v8ToIstanbul from "v8-to-istanbul";

async function convertCoverage() {
  const coverageDir = "./coverage";
  const files = fs.readdirSync(coverageDir).filter((f) => f.endsWith(".json"));

  const istanbulCoverage: any = {};

  for (const file of files) {
    const coverageData = JSON.parse(
      fs.readFileSync(path.join(coverageDir, file), "utf-8")
    );

    for (const entry of coverageData) {
      if (!entry.url.startsWith("file://")) continue;

      const filePath = entry.url.replace("file://", "");
      const converter = v8ToIstanbul(filePath);

      await converter.load();
      converter.applyCoverage(entry.functions || []);

      const istanbul = converter.toIstanbul();
      Object.assign(istanbulCoverage, istanbul);
    }
  }

  fs.writeFileSync(
    path.join(coverageDir, "coverage-final.json"),
    JSON.stringify(istanbulCoverage)
  );
}

convertCoverage();
```

### Generating HTML Report

```bash
# Using nyc to generate report
npx nyc report --reporter=html --reporter=text --temp-dir=./coverage
```

```typescript
// package.json scripts
{
  "scripts": {
    "test": "playwright test",
    "test:coverage": "playwright test && npm run coverage:report",
    "coverage:report": "npx nyc report --reporter=html --reporter=lcov --temp-dir=./coverage"
  }
}
```

### Custom Coverage Reporter

```typescript
// reporters/coverage-reporter.ts
import type { Reporter, FullResult } from "@playwright/test/reporter";
import fs from "fs";
import path from "path";

class CoverageReporter implements Reporter {
  private coverageData: any[] = [];

  onEnd(result: FullResult) {
    // Aggregate all coverage files
    const coverageDir = "./coverage";
    const files = fs
      .readdirSync(coverageDir)
      .filter((f) => f.endsWith(".json"));

    for (const file of files) {
      const data = JSON.parse(
        fs.readFileSync(path.join(coverageDir, file), "utf-8")
      );
      this.coverageData.push(...data);
    }

    // Generate summary
    const summary = this.generateSummary();
    console.log("\n📊 Coverage Summary:");
    console.log(`   Files: ${summary.totalFiles}`);
    console.log(`   Lines: ${summary.lineCoverage.toFixed(1)}%`);
    console.log(`   Bytes: ${summary.byteCoverage.toFixed(1)}%`);

    if (summary.lineCoverage < 80) {
      console.warn("⚠️  Coverage below 80% threshold!");
    }
  }

  private generateSummary() {
    let totalBytes = 0;
    let coveredBytes = 0;
    const files = new Set<string>();

    for (const entry of this.coverageData) {
      if (entry.url.includes("/src/")) {
        files.add(entry.url);
        totalBytes += entry.text?.length || 0;
        coveredBytes += entry.ranges.reduce(
          (sum: number, r: any) => sum + (r.end - r.start),
          0
        );
      }
    }

    return {
      totalFiles: files.size,
      byteCoverage: (coveredBytes / totalBytes) * 100,
      lineCoverage: (coveredBytes / totalBytes) * 100, // Simplified
    };
  }
}

export default CoverageReporter;
```

## Coverage Thresholds

### Enforcing Minimum Coverage

```typescript
// tests/coverage.spec.ts
import { test, expect } from "@playwright/test";
import fs from "fs";
import path from "path";

test.afterAll(async () => {
  const coverageDir = "./coverage";
  const files = fs.readdirSync(coverageDir).filter((f) => f.endsWith(".json"));

  let totalBytes = 0;
  let coveredBytes = 0;

  for (const file of files) {
    const coverage = JSON.parse(
      fs.readFileSync(path.join(coverageDir, file), "utf-8")
    );

    for (const entry of coverage) {
      if (!entry.url.includes("/src/")) continue;
      totalBytes += entry.text?.length || 0;
      coveredBytes += entry.ranges.reduce(
        (sum: number, r: any) => sum + (r.end - r.start),
        0
      );
    }
  }

  const coveragePercent = (coveredBytes / totalBytes) * 100;

  // Enforce threshold
  expect(coveragePercent).toBeGreaterThan(80);
});
```

### Per-Directory Thresholds

```typescript
// coverage-check.ts
interface CoverageThreshold {
  pattern: RegExp;
  minCoverage: number;
}

const thresholds: CoverageThreshold[] = [
  { pattern: /\/src\/core\//, minCoverage: 90 },
  { pattern: /\/src\/utils\//, minCoverage: 85 },
  { pattern: /\/src\/components\//, minCoverage: 70 },
  { pattern: /\/src\/pages\//, minCoverage: 60 },
];

function checkThresholds(coverage: any[]): string[] {
  const violations: string[] = [];

  for (const threshold of thresholds) {
    const matchingFiles = coverage.filter((c) => threshold.pattern.test(c.url));

    let total = 0;
    let covered = 0;

    for (const file of matchingFiles) {
      total += file.text?.length || 0;
      covered += file.ranges.reduce(
        (sum: number, r: any) => sum + (r.end - r.start),
        0
      );
    }

    const percent = total > 0 ? (covered / total) * 100 : 0;

    if (percent < threshold.minCoverage) {
      violations.push(
        `${threshold.pattern}: ${percent.toFixed(1)}% < ${
          threshold.minCoverage
        }%`
      );
    }
  }

  return violations;
}
```

## Advanced Patterns

### Merging Coverage Across Shards

```typescript
// scripts/merge-coverage.ts
import fs from "fs";
import { glob } from "glob";

async function mergeCoverage() {
  const files = await glob("shard-*/coverage/*.json");
  const merged = new Map<string, any>();

  for (const file of files) {
    const data = JSON.parse(fs.readFileSync(file, "utf-8"));
    for (const entry of data) {
      if (merged.has(entry.url)) {
        const existing = merged.get(entry.url);
        existing.ranges.push(...entry.ranges);
      } else {
        merged.set(entry.url, { ...entry });
      }
    }
  }

  fs.writeFileSync(
    "./coverage/merged.json",
    JSON.stringify([...merged.values()])
  );
}

mergeCoverage();
```

### Incremental Coverage

```typescript
// Check coverage only for changed files in CI
import { execSync } from "child_process";
import fs from "fs";

const changedFiles = execSync("git diff --name-only HEAD~1")
  .toString()
  .split("\n")
  .filter((f) => f.endsWith(".ts"));

const coverage = JSON.parse(fs.readFileSync("./coverage/merged.json", "utf-8"));

for (const file of changedFiles) {
  const entry = coverage.find((c: any) => c.url.includes(file));
  if (entry) {
    const percent =
      (entry.ranges.reduce((s: number, r: any) => s + r.end - r.start, 0) /
        (entry.text?.length || 1)) *
      100;
    console.log(`${file}: ${percent.toFixed(1)}%`);
  }
}
```

## CI Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests with Coverage

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 22

      - run: npm ci
      - run: npx playwright install --with-deps

      - name: Run tests with coverage
        run: npm run test:coverage

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/lcov.info
          fail_ci_if_error: true

      - name: Check coverage threshold
        run: |
          COVERAGE=$(cat coverage/coverage-summary.json | jq '.total.lines.pct')
          if (( $(echo "$COVERAGE < 80" | bc -l) )); then
            echo "Coverage $COVERAGE% is below 80% threshold"
            exit 1
          fi
```

## Anti-Patterns to Avoid

| Anti-Pattern                 | Problem                                | Solution                    |
| ---------------------------- | -------------------------------------- | --------------------------- |
| Coverage for coverage's sake | Gaming metrics                         | Focus on critical paths     |
| 100% coverage target         | Diminishing returns, tests for getters | Set realistic thresholds    |
| Ignoring coverage drops      | Technical debt                         | Enforce thresholds in CI    |
| No source map support        | Wrong line numbers                     | Enable source maps in build |
| Coverage only in CI          | Late feedback                          | Run locally too             |

## Related References

- **CI/CD**: See [ci-cd.md](ci-cd.md) for pipeline configuration
- **Performance**: See [performance.md](performance.md) for optimizing coverage collection
