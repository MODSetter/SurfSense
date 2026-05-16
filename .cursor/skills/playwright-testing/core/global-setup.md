# Global Setup & Teardown

## Table of Contents

1. [Global Setup](#global-setup)
2. [Global Teardown](#global-teardown)
3. [Database Patterns](#database-patterns)
4. [Environment Provisioning](#environment-provisioning)
5. [Setup Projects vs Global Setup](#setup-projects-vs-global-setup)
6. [Parallel Execution Caveats](#parallel-execution-caveats)

## Global Setup

### Basic Global Setup

```typescript
// global-setup.ts
import { FullConfig } from "@playwright/test";

async function globalSetup(config: FullConfig) {
  console.log("Running global setup...");
  // Perform one-time setup: start services, run migrations, etc.
}

export default globalSetup;
```

### Configure Global Setup

```typescript
// playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  globalSetup: require.resolve("./global-setup"),
  globalTeardown: require.resolve("./global-teardown"),
});
```

> **Authentication in Global Setup**: For authentication patterns using storage state in global setup, see [fixtures-hooks.md](fixtures-hooks.md#authentication-patterns). Setup projects are generally preferred for authentication as they provide access to Playwright fixtures.

### Global Setup with Return Value

```typescript
// global-setup.ts
async function globalSetup(config: FullConfig): Promise<() => Promise<void>> {
  const server = await startTestServer();

  // Return cleanup function (alternative to globalTeardown)
  return async () => {
    await server.stop();
  };
}

export default globalSetup;
```

### Access Config in Global Setup

```typescript
// global-setup.ts
import { FullConfig } from "@playwright/test";

async function globalSetup(config: FullConfig) {
  const { baseURL } = config.projects[0].use;
  console.log(`Setting up for ${baseURL}`);

  // Access custom config
  const workers = config.workers;
  const timeout = config.timeout;

  // Access environment
  const isCI = !!process.env.CI;
}

export default globalSetup;
```

## Global Teardown

### Basic Global Teardown

```typescript
// global-teardown.ts
import { FullConfig } from "@playwright/test";
import fs from "fs";

async function globalTeardown(config: FullConfig) {
  console.log("Running global teardown...");

  // Clean up auth files
  if (fs.existsSync(".auth")) {
    fs.rmSync(".auth", { recursive: true });
  }

  // Clean up test data
  await cleanupTestDatabase();

  // Stop services
  await stopTestServices();
}

export default globalTeardown;
```

### Conditional Teardown

```typescript
// global-teardown.ts
async function globalTeardown(config: FullConfig) {
  // Skip cleanup in CI (containers are discarded anyway)
  if (process.env.CI) {
    console.log("Skipping teardown in CI");
    return;
  }

  // Local cleanup
  await cleanupLocalTestData();
}

export default globalTeardown;
```

## Database Patterns

This section covers **one-time database setup** (migrations, snapshots, per-worker databases). For related topics:

- **Per-test database fixtures** (isolation, transaction rollback): See [fixtures-hooks.md](fixtures-hooks.md#database-fixtures)
- **Test data factories** (builders, Faker): See [test-data.md](test-data.md)

### Database Migration in Setup

```typescript
// global-setup.ts
import { execSync } from "child_process";

async function globalSetup() {
  console.log("Running database migrations...");

  // Run migrations
  execSync("npx prisma migrate deploy", { stdio: "inherit" });

  // Seed test data
  execSync("npx prisma db seed", { stdio: "inherit" });
}

export default globalSetup;
```

### Database Snapshot Pattern

```typescript
// global-setup.ts
import { execSync } from "child_process";
import fs from "fs";

const SNAPSHOT_PATH = "./test-db-snapshot.sql";

async function globalSetup() {
  // Check if snapshot exists
  if (fs.existsSync(SNAPSHOT_PATH)) {
    console.log("Restoring database from snapshot...");
    execSync(`psql $DATABASE_URL < ${SNAPSHOT_PATH}`, { stdio: "inherit" });
    return;
  }

  // First run: migrate and create snapshot
  console.log("Creating database snapshot...");
  execSync("npx prisma migrate deploy", { stdio: "inherit" });
  execSync("npx prisma db seed", { stdio: "inherit" });
  execSync(`pg_dump $DATABASE_URL > ${SNAPSHOT_PATH}`, { stdio: "inherit" });
}

export default globalSetup;
```

### Test Database per Worker

```typescript
// global-setup.ts
async function globalSetup(config: FullConfig) {
  const workerCount = config.workers || 1;

  // Create a database for each worker
  for (let i = 0; i < workerCount; i++) {
    const dbName = `test_db_worker_${i}`;
    await createDatabase(dbName);
    await runMigrations(dbName);
    await seedDatabase(dbName);
  }
}

// global-teardown.ts
async function globalTeardown(config: FullConfig) {
  const workerCount = config.workers || 1;

  for (let i = 0; i < workerCount; i++) {
    await dropDatabase(`test_db_worker_${i}`);
  }
}
```

## Environment Provisioning

### Start Services in Setup

```typescript
// global-setup.ts
import { execSync, spawn } from "child_process";

let serverProcess: any;

async function globalSetup() {
  // Start backend server
  serverProcess = spawn("npm", ["run", "start:test"], {
    stdio: "pipe",
    detached: true,
  });

  // Wait for server to be ready
  await waitForServer("http://localhost:3000/health", 30000);

  // Store PID for teardown
  process.env.SERVER_PID = serverProcess.pid.toString();
}

async function waitForServer(url: string, timeout: number) {
  const start = Date.now();

  while (Date.now() - start < timeout) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Server not ready yet
    }
    await new Promise((r) => setTimeout(r, 1000));
  }

  throw new Error(`Server did not start within ${timeout}ms`);
}

export default globalSetup;
```

### Docker Compose Setup

```typescript
// global-setup.ts
import { execSync } from "child_process";

async function globalSetup() {
  console.log("Starting Docker services...");

  execSync("docker-compose -f docker-compose.test.yml up -d", {
    stdio: "inherit",
  });

  // Wait for services to be healthy
  execSync("docker-compose -f docker-compose.test.yml exec -T db pg_isready", {
    stdio: "inherit",
  });
}

export default globalSetup;
```

```typescript
// global-teardown.ts
import { execSync } from "child_process";

async function globalTeardown() {
  console.log("Stopping Docker services...");

  execSync("docker-compose -f docker-compose.test.yml down -v", {
    stdio: "inherit",
  });
}

export default globalTeardown;
```

### Environment Variables Setup

```typescript
// global-setup.ts
import dotenv from "dotenv";
import path from "path";

async function globalSetup() {
  // Load test-specific environment
  const envFile = process.env.CI ? ".env.ci" : ".env.test";
  dotenv.config({ path: path.resolve(process.cwd(), envFile) });

  // Validate required variables
  const required = ["DATABASE_URL", "API_KEY", "TEST_EMAIL"];
  for (const key of required) {
    if (!process.env[key]) {
      throw new Error(`Missing required environment variable: ${key}`);
    }
  }
}

export default globalSetup;
```

## Setup Projects vs Global Setup

### When to Use Each

| Use Global Setup                      | Use Setup Projects                       |
| ------------------------------------- | ---------------------------------------- |
| One-time setup (migrations, services) | Per-project setup (auth states)          |
| No access to Playwright fixtures      | Need page, request fixtures              |
| Runs once before all projects         | Can run per-project or have dependencies |
| Shared across all workers             | Can be parallelized                      |

### Setup Project Pattern

```typescript
// playwright.config.ts
export default defineConfig({
  projects: [
    // Setup project
    {
      name: "setup",
      testMatch: /.*\.setup\.ts/,
    },
    // Test projects depend on setup
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
      dependencies: ["setup"],
    },
  ],
});
```

> **For complete authentication setup patterns**, see [fixtures-hooks.md](fixtures-hooks.md#authentication-patterns).

### Combining Both

```typescript
// playwright.config.ts
export default defineConfig({
  // Global: Start services, run migrations
  globalSetup: require.resolve("./global-setup"),
  globalTeardown: require.resolve("./global-teardown"),

  projects: [
    // Setup project: Create auth states
    { name: "setup", testMatch: /.*\.setup\.ts/ },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: ".auth/user.json",
      },
      dependencies: ["setup"],
    },
  ],
});
```

## Parallel Execution Caveats

### Understanding Global Setup Execution

```
┌─────────────────────────────────────────────────────────────┐
│  globalSetup runs ONCE                                      │
│  ↓                                                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ Worker 1│  │ Worker 2│  │ Worker 3│  │ Worker 4│        │
│  │ tests   │  │ tests   │  │ tests   │  │ tests   │        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
│  ↓                                                          │
│  globalTeardown runs ONCE                                   │
└─────────────────────────────────────────────────────────────┘
```

**Key implications:**

- Global setup has **no access** to Playwright fixtures (`page`, `request`, `context`)
- State created in global setup is **shared** across all workers
- If tests **modify** shared state, they may conflict with parallel workers
- Global setup **cannot** react to individual test needs

### When to Prefer Worker-Scoped Fixtures

Use **worker-scoped fixtures** instead of globalSetup when:

| Scenario                             | Why Fixtures Are Better                              |
| ------------------------------------ | ---------------------------------------------------- |
| Each worker needs isolated resources | Fixtures can create per-worker databases, servers    |
| Setup needs Playwright APIs          | Fixtures have access to `page`, `request`, `browser` |
| Setup depends on test configuration  | Fixtures receive test context and options            |
| Resources need cleanup per worker    | Worker fixtures auto-cleanup when worker exits       |

### Common Parallel Pitfall

```typescript
// ❌ BAD: Global setup creates ONE user, all workers fight over it
async function globalSetup() {
  await createUser({ email: "test@example.com" }); // Shared!
}

// ✅ GOOD: Each worker gets its own user via worker-scoped fixture
// Uses workerInfo.workerIndex to create unique data per worker
```

> **For worker-scoped fixture patterns** (per-worker databases, unique test data, `workerIndex` isolation), see [fixtures-hooks.md](fixtures-hooks.md#isolate-test-data-between-parallel-workers).

## Anti-Patterns to Avoid

| Anti-Pattern                   | Problem                          | Solution                                   |
| ------------------------------ | -------------------------------- | ------------------------------------------ |
| Heavy setup in globalSetup     | Slow test startup                | Use setup projects for parallelizable work |
| Not cleaning up in teardown    | Leaks resources, flaky CI        | Always clean up or use containers          |
| Hardcoded URLs in setup        | Breaks in different environments | Use config.projects[0].use.baseURL         |
| No timeout on service wait     | Hangs forever if service fails   | Add timeout with clear error               |
| Shared mutable state           | Race conditions in parallel      | Use worker-scoped fixtures for isolation   |
| Global setup for per-test data | Tests conflict                   | Use test-scoped fixtures                   |

## Related References

- **Fixtures & Auth**: See [fixtures-hooks.md](fixtures-hooks.md) for worker-scoped fixtures and auth patterns
- **CI/CD**: See [ci-cd.md](../infrastructure-ci-cd/ci-cd.md) for CI setup patterns
- **Projects**: See [projects-dependencies.md](projects-dependencies.md) for project configuration
