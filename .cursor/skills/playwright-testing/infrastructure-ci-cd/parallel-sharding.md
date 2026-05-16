# Sharding and Parallel Execution

## Table of Contents

1. [CLI Commands](#cli-commands)
2. [Patterns](#patterns)
3. [Decision Guide](#decision-guide)
4. [Anti-Patterns](#anti-patterns)
5. [Troubleshooting](#troubleshooting)

> **When to use**: Speeding up test suites by running tests concurrently on one machine (workers) or splitting across multiple CI jobs (sharding).

## CLI Commands

```bash
# Parallelism within one machine
npx playwright test --workers=4
npx playwright test --workers=50%

# Splitting across CI jobs
npx playwright test --shard=1/4
npx playwright test --shard=2/4

# Merging shard outputs
npx playwright merge-reports ./blob-report
npx playwright merge-reports --reporter=html,json ./blob-report

# Override config for single run
npx playwright test --fully-parallel
```

## Patterns

### Worker Configuration

**Use when**: Controlling concurrent test execution on a single machine.

```ts
// playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  // Tests WITHIN a file also run in parallel
  fullyParallel: true,

  // Worker count options:
  // - undefined: auto-detect (half CPU cores)
  // - number: fixed count
  // - string: percentage of cores
  workers: process.env.CI ? "50%" : undefined,
});
```

**`fullyParallel` behavior:**

| Setting                          | Files parallel | Tests in file parallel |
| -------------------------------- | -------------- | ---------------------- |
| `fullyParallel: false` (default) | Yes            | No (serial)            |
| `fullyParallel: true`            | Yes            | Yes                    |

**Serial execution for specific files:**

```ts
// tests/checkout-flow.spec.ts
import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

test("add items to cart", async ({ page }) => {
  // ...
});

test("complete payment", async ({ page }) => {
  // ...
});
```

### Sharding Across CI Machines

**Use when**: Suite exceeds 5 minutes even with maximum workers.

```bash
# Job 1            Job 2            Job 3            Job 4
--shard=1/4        --shard=2/4      --shard=3/4      --shard=4/4
```

**Config for sharded runs:**

```ts
// playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  fullyParallel: true,
  workers: process.env.CI ? "50%" : undefined,

  reporter: process.env.CI
    ? [["blob"], ["github"]]
    : [["html", { open: "on-failure" }]],
});
```

### Merging Shard Reports

**Use when**: Combining blob reports from multiple shards into a unified report.

```bash
# Merge all blobs into HTML
npx playwright merge-reports --reporter=html ./all-blob-reports

# Multiple formats
npx playwright merge-reports --reporter=html,json,junit ./all-blob-reports

# Custom output location
PLAYWRIGHT_HTML_REPORT=merged-report npx playwright merge-reports --reporter=html ./all-blob-reports
```

**GitHub Actions merge job:**

```yaml
merge-reports:
  if: ${{ !cancelled() }}
  needs: test
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - run: npm ci

    - uses: actions/download-artifact@v4
      with:
        path: all-blob-reports
        pattern: blob-report-*
        merge-multiple: true

    - run: npx playwright merge-reports --reporter=html ./all-blob-reports

    - uses: actions/upload-artifact@v4
      with:
        name: playwright-report
        path: playwright-report/
        retention-days: 14
```

### Worker-Scoped Fixtures

**Use when**: Expensive resources (DB connections, auth tokens) should be created once per worker, not per test.

```ts
// fixtures.ts
import { test as base } from "@playwright/test";

type WorkerFixtures = {
  dbClient: DatabaseClient;
  apiToken: string;
};

export const test = base.extend<{}, WorkerFixtures>({
  dbClient: [
    async ({}, use) => {
      const client = await DatabaseClient.connect(process.env.DB_URL!);
      await use(client);
      await client.disconnect();
    },
    { scope: "worker" },
  ],

  apiToken: [
    async ({}, use, workerInfo) => {
      const res = await fetch(`${process.env.API_URL}/auth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user: `test-user-${workerInfo.workerIndex}`,
          password: process.env.TEST_PASSWORD,
        }),
      });
      const { token } = await res.json();
      await use(token);
    },
    { scope: "worker" },
  ],
});

export { expect } from "@playwright/test";
```

### Test Isolation for Parallelism

**Use when**: Preparing tests to run without interference.

Each test must create its own state. No test should depend on or modify shared state.

```ts
// BAD: Shared user causes race conditions
test("edit settings", async ({ page }) => {
  await page.goto("/users/test-user/settings");
  await page.getByLabel("Email").fill("new@example.com");
  await page.getByRole("button", { name: "Save" }).click();
});

// GOOD: Unique user per test
test("edit settings", async ({ page, request }) => {
  const res = await request.post("/api/users", {
    data: { name: `user-${Date.now()}`, email: `${Date.now()}@test.com` },
  });
  const user = await res.json();

  await page.goto(`/users/${user.id}/settings`);
  await page.getByLabel("Email").fill("updated@example.com");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByLabel("Email")).toHaveValue("updated@example.com");

  await request.delete(`/api/users/${user.id}`);
});
```

**Using `testInfo` for unique identifiers:**

```ts
import { test, expect } from "@playwright/test";

test("submit order", async ({ page }, testInfo) => {
  const orderId = `order-${testInfo.workerIndex}-${Date.now()}`;
  await page.goto(`/orders/new?ref=${orderId}`);
  // ...
});
```

### Dynamic Shard Count

**Use when**: Automatically adjusting shards based on test count.

```yaml
# .github/workflows/playwright.yml
jobs:
  calculate-shards:
    runs-on: ubuntu-latest
    outputs:
      shard-count: ${{ steps.calc.outputs.count }}
      shard-matrix: ${{ steps.calc.outputs.matrix }}
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - id: calc
        run: |
          TEST_COUNT=$(npx playwright test --list --reporter=json 2>/dev/null | node -e "
            const data = require('fs').readFileSync('/dev/stdin', 'utf8');
            const parsed = JSON.parse(data);
            console.log(parsed.suites?.reduce((acc, s) => acc + (s.specs?.length || 0), 0) || 0);
          ")
          # 1 shard per 20 tests, min 1, max 8
          SHARDS=$(( (TEST_COUNT + 19) / 20 ))
          SHARDS=$(( SHARDS > 8 ? 8 : SHARDS ))
          SHARDS=$(( SHARDS < 1 ? 1 : SHARDS ))
          MATRIX="["
          for i in $(seq 1 $SHARDS); do
            [ $i -gt 1 ] && MATRIX+=","
            MATRIX+="\"$i/$SHARDS\""
          done
          MATRIX+="]"
          echo "count=$SHARDS" >> $GITHUB_OUTPUT
          echo "matrix=$MATRIX" >> $GITHUB_OUTPUT

  test:
    needs: calculate-shards
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: ${{ fromJson(needs.calculate-shards.outputs.shard-matrix) }}
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx playwright install --with-deps
      - run: npx playwright test --shard=${{ matrix.shard }}
```

## Decision Guide

| Scenario                         | Workers        | Shards | Reason                                  |
| -------------------------------- | -------------- | ------ | --------------------------------------- |
| < 50 tests, < 5 min              | Auto (default) | None   | No optimization needed                  |
| 50-200 tests, 5-15 min           | `'50%'` in CI  | 2-4    | Balance speed and cost                  |
| 200+ tests, > 15 min             | `'50%'` in CI  | 4-8    | Keep feedback under 10 min              |
| Flaky due to resource contention | Reduce to 2    | Keep   | Less CPU/memory pressure                |
| Tests modify shared database     | 1 or isolate   | Useful | Sharding splits files; workers run them |
| CI has limited resources         | 1 or `'25%'`   | More   | Compensate with more machines           |

| Aspect         | Workers (in-process)      | Shards (across machines)   |
| -------------- | ------------------------- | -------------------------- |
| What it splits | Tests across CPU cores    | Test files across CI jobs  |
| Controlled by  | Config or `--workers` CLI | `--shard=X/Y` CLI flag     |
| Shares memory  | Yes                       | No                         |
| Report merging | Not needed                | Required (`merge-reports`) |
| Cost           | Free (same machine)       | More CI minutes            |

## Anti-Patterns

| Anti-Pattern                            | Problem                                  | Solution                                             |
| --------------------------------------- | ---------------------------------------- | ---------------------------------------------------- |
| `fullyParallel: false` without reason   | Tests in files run serially              | Set `fullyParallel: true` unless tests need serial   |
| `workers: 1` in CI "for safety"         | Negates parallelism                      | Fix isolation issues; use `workers: '50%'`           |
| Hardcoded shared user account           | Race conditions in parallel runs         | Each test creates unique data                        |
| Sharding without blob reporter          | Each shard produces separate HTML report | Configure `reporter: [['blob']]` for CI              |
| Sharding with 3 tests                   | Setup overhead exceeds time saved        | Only shard when suite > 5 minutes                    |
| `test.describe.serial()` everywhere     | Kills parallelism, creates dependencies  | Use only when tests genuinely need prior state       |
| Workers > CPU cores                     | Context switching overhead               | Use `'50%'` or auto-detect                           |
| Missing `fail-fast: false` in CI matrix | One shard failure cancels others         | Always set `fail-fast: false` for sharded strategies |

## Troubleshooting

### Tests pass solo but fail together

- **Shared state**. Make test data unique:
  ```ts
  test("create item", async ({ request }, ti) => {
    await request.post("/api/items", {
      data: { name: `Item-${ti.workerIndex}-${Date.now()}` },
    });
  });
  ```

### "No tests found" in some shards

- **Too many shards**. Never exceed file count:
  ```bash
  npx playwright test --shard=1/10   # ok if 10 files
  npx playwright test --shard=1/20   # too many, some shards empty
  ```

### Merged report missing results

- **Blob reports collide**. Use unique names:
  ```yaml
  # Each shard
  - uses: actions/upload-artifact@v4
    with:
      name: blob-report-${{ strategy.job-index }}
      path: blob-report/
  # Merge step
  - uses: actions/download-artifact@v4
    with:
      pattern: blob-report-*
      merge-multiple: true
      path: all-blob-reports
  ```

### Worker-scoped fixture not working

- **Missing `{ scope: 'worker' }`**. Fix:
  ```ts
  export const test = base.extend({
    resource: [
      async ({}, use) => {
        const r = await Resource.create();
        await use(r);
        await r.destroy();
      },
      { scope: "worker" },
    ],
  });
  ```

### More workers = Slower

- **Too many workers thrash**. Limit in CI:
  ```ts
  export default defineConfig({
    workers: process.env.CI ? 2 : undefined,
  });
  ```
