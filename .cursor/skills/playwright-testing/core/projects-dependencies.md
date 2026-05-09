# Projects & Dependencies

## Table of Contents

1. [Project Configuration](#project-configuration)
2. [Project Dependencies](#project-dependencies)
3. [Setup Projects](#setup-projects)
4. [Filtering & Running Projects](#filtering--running-projects)
5. [Sharing Configuration](#sharing-configuration)
6. [Advanced Patterns](#advanced-patterns)

## Project Configuration

### Basic Multi-Browser Setup

```typescript
// playwright.config.ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
  ],
});
```

### Environment-Based Projects

```typescript
export default defineConfig({
  projects: [
    {
      name: "staging",
      use: {
        baseURL: "https://staging.example.com",
      },
    },
    {
      name: "production",
      use: {
        baseURL: "https://example.com",
      },
    },
    {
      name: "local",
      use: {
        baseURL: "http://localhost:3000",
      },
    },
  ],
});
```

### Test Type Projects

```typescript
export default defineConfig({
  projects: [
    {
      name: "e2e",
      testDir: "./tests/e2e",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "api",
      testDir: "./tests/api",
      use: { baseURL: "http://localhost:3000" },
    },
    {
      name: "visual",
      testDir: "./tests/visual",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 720 },
      },
    },
  ],
});
```

## Project Dependencies

### Setup Dependency

```typescript
export default defineConfig({
  projects: [
    // Setup project runs first
    {
      name: "setup",
      testMatch: /.*\.setup\.ts/,
    },

    // Browser projects depend on setup
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: ".auth/user.json",
      },
      dependencies: ["setup"],
    },
    {
      name: "firefox",
      use: {
        ...devices["Desktop Firefox"],
        storageState: ".auth/user.json",
      },
      dependencies: ["setup"],
    },
  ],
});
```

### Multiple Auth States

```typescript
export default defineConfig({
  projects: [
    // Auth setup projects
    {
      name: "setup-admin",
      testMatch: /admin\.setup\.ts/,
    },
    {
      name: "setup-user",
      testMatch: /user\.setup\.ts/,
    },

    // Admin tests
    {
      name: "admin-tests",
      testDir: "./tests/admin",
      use: { storageState: ".auth/admin.json" },
      dependencies: ["setup-admin"],
    },

    // User tests
    {
      name: "user-tests",
      testDir: "./tests/user",
      use: { storageState: ".auth/user.json" },
      dependencies: ["setup-user"],
    },

    // Tests that need both
    {
      name: "integration-tests",
      testDir: "./tests/integration",
      dependencies: ["setup-admin", "setup-user"],
    },
  ],
});
```

### Chained Dependencies

```typescript
export default defineConfig({
  projects: [
    // Step 1: Database setup
    {
      name: "db-setup",
      testMatch: /db\.setup\.ts/,
    },

    // Step 2: Auth setup (needs DB)
    {
      name: "auth-setup",
      testMatch: /auth\.setup\.ts/,
      dependencies: ["db-setup"],
    },

    // Step 3: Seed data (needs auth)
    {
      name: "seed-setup",
      testMatch: /seed\.setup\.ts/,
      dependencies: ["auth-setup"],
    },

    // Tests (need everything)
    {
      name: "tests",
      testDir: "./tests",
      dependencies: ["seed-setup"],
    },
  ],
});
```

## Setup Projects

### Authentication Setup

Setup projects are the recommended way to handle authentication. They run before your main test projects and can use Playwright fixtures.

> **For complete authentication patterns** (storage state, multiple auth states, auth fixtures), see [fixtures-hooks.md](fixtures-hooks.md#authentication-patterns).

### Data Seeding Setup

```typescript
// seed.setup.ts
import { test as setup } from "@playwright/test";

setup("seed test data", async ({ request }) => {
  // Create test data via API
  await request.post("/api/test/seed", {
    data: {
      users: 10,
      products: 50,
      orders: 100,
    },
  });
});
```

### Cleanup Setup

```typescript
// cleanup.setup.ts
import { test as setup } from "@playwright/test";

setup("cleanup previous run", async ({ request }) => {
  // Clean up data from previous test runs
  await request.delete("/api/test/cleanup");
});
```

## Filtering & Running Projects

### Run Specific Project

```bash
# Run single project
npx playwright test --project=chromium

# Run multiple projects
npx playwright test --project=chromium --project=firefox
```

### Run by Grep

```bash
# Run tests matching pattern
npx playwright test --grep @smoke

# Run project with grep
npx playwright test --project=chromium --grep @critical

# Exclude pattern
npx playwright test --grep-invert @slow
```

### Project-Specific Grep

```typescript
export default defineConfig({
  projects: [
    {
      name: "smoke",
      grep: /@smoke/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "regression",
      grepInvert: /@smoke/,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
```

## Sharing Configuration

### Base Configuration

```typescript
// playwright.config.ts
const baseConfig = {
  timeout: 30000,
  expect: { timeout: 5000 },
  use: {
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
};

export default defineConfig({
  ...baseConfig,
  projects: [
    {
      name: "chromium",
      use: {
        ...baseConfig.use,
        ...devices["Desktop Chrome"],
      },
    },
    {
      name: "firefox",
      use: {
        ...baseConfig.use,
        ...devices["Desktop Firefox"],
      },
    },
  ],
});
```

### Shared Project Settings

```typescript
const sharedBrowserConfig = {
  timeout: 60000,
  retries: 2,
  use: {
    video: "on-first-retry",
    trace: "on-first-retry",
  },
};

export default defineConfig({
  projects: [
    {
      name: "chromium",
      ...sharedBrowserConfig,
      use: {
        ...sharedBrowserConfig.use,
        ...devices["Desktop Chrome"],
      },
    },
    {
      name: "firefox",
      ...sharedBrowserConfig,
      use: {
        ...sharedBrowserConfig.use,
        ...devices["Desktop Firefox"],
      },
    },
  ],
});
```

## Advanced Patterns

### Conditional Projects

```typescript
const projects = [
  {
    name: "chromium",
    use: { ...devices["Desktop Chrome"] },
  },
];

// Add Firefox only in CI
if (process.env.CI) {
  projects.push({
    name: "firefox",
    use: { ...devices["Desktop Firefox"] },
  });
}

// Add mobile only for specific test dirs
if (process.env.TEST_MOBILE) {
  projects.push({
    name: "mobile",
    use: { ...devices["iPhone 14"] },
  });
}

export default defineConfig({ projects });
```

### Project Metadata

```typescript
export default defineConfig({
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      metadata: {
        platform: "desktop",
        browser: "chromium",
        priority: "high",
      },
    },
  ],
});

// Access in test
test("example", async ({ page }, testInfo) => {
  const { platform, priority } = testInfo.project.metadata;
  console.log(`Running on ${platform} with ${priority} priority`);
});
```

### Teardown Projects

```typescript
export default defineConfig({
  projects: [
    {
      name: "setup",
      testMatch: /.*\.setup\.ts/,
      teardown: "teardown", // Run teardown after this completes
    },
    {
      name: "teardown",
      testMatch: /.*\.teardown\.ts/,
    },
    {
      name: "tests",
      dependencies: ["setup"],
    },
  ],
});
```

```typescript
// cleanup.teardown.ts
import { test as teardown } from "@playwright/test";

teardown("cleanup", async ({ request }) => {
  await request.delete("/api/test/data");
});
```

## Anti-Patterns to Avoid

| Anti-Pattern               | Problem                | Solution                            |
| -------------------------- | ---------------------- | ----------------------------------- |
| Too many browser projects  | Slow CI, expensive     | Focus on critical browsers          |
| Missing setup dependencies | Tests fail randomly    | Declare all dependencies explicitly |
| Duplicated configuration   | Hard to maintain       | Extract shared config               |
| Not using setup projects   | Repeated auth in tests | Use setup project + storageState    |

## Related References

- **Global Setup**: See [global-setup.md](global-setup.md) for globalSetup vs setup projects
- **Fixtures**: See [fixtures-hooks.md](fixtures-hooks.md) for authentication patterns
- **CI/CD**: See [ci-cd.md](../infrastructure-ci-cd/ci-cd.md) for running projects in CI
