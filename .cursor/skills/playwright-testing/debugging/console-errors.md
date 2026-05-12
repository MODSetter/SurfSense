# Browser Console & JavaScript Error Handling

## Table of Contents

1. [Capturing Console Messages](#capturing-console-messages)
2. [Failing on Console Errors](#failing-on-console-errors)
3. [JavaScript Error Detection](#javascript-error-detection)
4. [Monitoring Warnings](#monitoring-warnings)
5. [Console Fixtures](#console-fixtures)

## Capturing Console Messages

### Basic Console Capture

```typescript
test("capture console logs", async ({ page }) => {
  const logs: string[] = [];

  page.on("console", (msg) => {
    logs.push(`${msg.type()}: ${msg.text()}`);
  });

  await page.goto("/");

  // Check what was logged
  console.log("Captured logs:", logs);
});
```

### Capture by Type

```typescript
test("capture specific console types", async ({ page }) => {
  const errors: string[] = [];
  const warnings: string[] = [];
  const infos: string[] = [];

  page.on("console", (msg) => {
    switch (msg.type()) {
      case "error":
        errors.push(msg.text());
        break;
      case "warning":
        warnings.push(msg.text());
        break;
      case "info":
      case "log":
        infos.push(msg.text());
        break;
    }
  });

  await page.goto("/dashboard");

  expect(errors).toHaveLength(0);
  console.log("Warnings:", warnings);
});
```

### Capture with Stack Trace

```typescript
test("capture errors with location", async ({ page }) => {
  const errors: { message: string; location?: string }[] = [];

  page.on("console", async (msg) => {
    if (msg.type() === "error") {
      const location = msg.location();
      errors.push({
        message: msg.text(),
        location: location
          ? `${location.url}:${location.lineNumber}`
          : undefined,
      });
    }
  });

  await page.goto("/buggy-page");

  // Log errors with source location
  errors.forEach((e) => {
    console.log(`Error: ${e.message}`);
    if (e.location) console.log(`  at ${e.location}`);
  });
});
```

## Failing on Console Errors

### Fail Test on Any Error

```typescript
test("no console errors allowed", async ({ page }) => {
  const errors: string[] = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      errors.push(msg.text());
    }
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Load Data" }).click();

  // Fail if any console errors
  expect(errors, `Console errors found:\n${errors.join("\n")}`).toHaveLength(0);
});
```

### Fail with Allowed Exceptions

```typescript
test("no unexpected console errors", async ({ page }) => {
  const allowedErrors = [
    /Failed to load resource.*favicon/,
    /ResizeObserver loop/,
  ];

  const unexpectedErrors: string[] = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      const isAllowed = allowedErrors.some((pattern) => pattern.test(text));
      if (!isAllowed) {
        unexpectedErrors.push(text);
      }
    }
  });

  await page.goto("/");

  expect(
    unexpectedErrors,
    `Unexpected console errors:\n${unexpectedErrors.join("\n")}`,
  ).toHaveLength(0);
});
```

### Auto-Fail Fixture

```typescript
// fixtures/console.fixture.ts
type ConsoleFixtures = {
  failOnConsoleError: void;
};

export const test = base.extend<ConsoleFixtures>({
  failOnConsoleError: [
    async ({ page }, use, testInfo) => {
      const errors: string[] = [];

      page.on("console", (msg) => {
        if (msg.type() === "error") {
          errors.push(msg.text());
        }
      });

      await use();

      // After test, check for errors
      if (errors.length > 0) {
        testInfo.annotations.push({
          type: "console-errors",
          description: errors.join("\n"),
        });
        throw new Error(`Console errors detected:\n${errors.join("\n")}`);
      }
    },
    { auto: true }, // Runs for every test
  ],
});
```

## JavaScript Error Detection

### Catch Uncaught Exceptions

```typescript
test("no uncaught exceptions", async ({ page }) => {
  const pageErrors: Error[] = [];

  page.on("pageerror", (error) => {
    pageErrors.push(error);
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Trigger Action" }).click();

  expect(
    pageErrors,
    `Uncaught exceptions:\n${pageErrors.map((e) => e.message).join("\n")}`,
  ).toHaveLength(0);
});
```

### Capture Error Details

```typescript
test("capture JS error details", async ({ page }) => {
  const errors: { message: string; stack?: string }[] = [];

  page.on("pageerror", (error) => {
    errors.push({
      message: error.message,
      stack: error.stack,
    });
  });

  await page.goto("/error-page");

  if (errors.length > 0) {
    console.log("JavaScript errors:");
    errors.forEach((e) => {
      console.log(`  Message: ${e.message}`);
      console.log(`  Stack: ${e.stack}`);
    });
  }
});
```

### Test Error Boundary Triggers

```typescript
test("error boundary catches render error", async ({ page }) => {
  let errorCaught = false;

  page.on("pageerror", () => {
    // Note: React error boundaries catch errors before they become pageerrors
    // This would only fire for unhandled errors
    errorCaught = true;
  });

  // Trigger component error via props
  await page.route(
    "**/api/data",
    (route) => route.fulfill({ json: null }), // Will cause "cannot read property of null"
  );

  await page.goto("/dashboard");

  // Error boundary should show fallback, not crash
  await expect(page.getByText("Something went wrong")).toBeVisible();
  expect(errorCaught).toBe(false); // Error was caught by boundary
});
```

## Monitoring Warnings

### Capture Deprecation Warnings

```typescript
test("no deprecation warnings", async ({ page }) => {
  const deprecations: string[] = [];

  page.on("console", (msg) => {
    const text = msg.text();
    if (
      msg.type() === "warning" &&
      (text.includes("deprecated") || text.includes("Deprecation"))
    ) {
      deprecations.push(text);
    }
  });

  await page.goto("/");

  if (deprecations.length > 0) {
    console.warn("Deprecation warnings found:");
    deprecations.forEach((d) => console.warn(`  - ${d}`));
  }

  // Optionally fail
  // expect(deprecations).toHaveLength(0);
});
```

### React Development Warnings

```typescript
test("no React warnings", async ({ page }) => {
  const reactWarnings: string[] = [];

  page.on("console", (msg) => {
    const text = msg.text();
    if (
      msg.type() === "warning" &&
      (text.includes("Warning:") || text.includes("React"))
    ) {
      reactWarnings.push(text);
    }
  });

  await page.goto("/");

  // Common React warnings to check
  const criticalWarnings = reactWarnings.filter(
    (w) =>
      w.includes("Each child in a list should have a unique") ||
      w.includes("Cannot update a component") ||
      w.includes("Can't perform a React state update"),
  );

  expect(
    criticalWarnings,
    `React warnings:\n${criticalWarnings.join("\n")}`,
  ).toHaveLength(0);
});
```

## Console Fixtures

### Comprehensive Console Fixture

```typescript
// fixtures/console.fixture.ts
type ConsoleMessage = {
  type: string;
  text: string;
  location?: { url: string; line: number };
  timestamp: number;
};

type ConsoleFixtures = {
  consoleMessages: ConsoleMessage[];
  getConsoleErrors: () => ConsoleMessage[];
  getConsoleWarnings: () => ConsoleMessage[];
  assertNoErrors: (allowedPatterns?: RegExp[]) => void;
};

export const test = base.extend<ConsoleFixtures>({
  consoleMessages: async ({ page }, use) => {
    const messages: ConsoleMessage[] = [];

    page.on("console", (msg) => {
      const location = msg.location();
      messages.push({
        type: msg.type(),
        text: msg.text(),
        location: location
          ? { url: location.url, line: location.lineNumber }
          : undefined,
        timestamp: Date.now(),
      });
    });

    await use(messages);
  },

  getConsoleErrors: async ({ consoleMessages }, use) => {
    await use(() => consoleMessages.filter((m) => m.type === "error"));
  },

  getConsoleWarnings: async ({ consoleMessages }, use) => {
    await use(() => consoleMessages.filter((m) => m.type === "warning"));
  },

  assertNoErrors: async ({ getConsoleErrors }, use) => {
    await use((allowedPatterns = []) => {
      const errors = getConsoleErrors();
      const unexpected = errors.filter(
        (e) => !allowedPatterns.some((p) => p.test(e.text)),
      );

      if (unexpected.length > 0) {
        throw new Error(
          `Unexpected console errors:\n${unexpected.map((e) => e.text).join("\n")}`,
        );
      }
    });
  },
});

// Usage
test("page loads without errors", async ({ page, assertNoErrors }) => {
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Load" }).click();

  assertNoErrors([/favicon/]); // Allow favicon errors
});
```

### Attach Console to Report

```typescript
test("capture console for debugging", async ({ page }, testInfo) => {
  const logs: string[] = [];

  page.on("console", (msg) => {
    logs.push(`[${msg.type()}] ${msg.text()}`);
  });

  page.on("pageerror", (error) => {
    logs.push(`[EXCEPTION] ${error.message}`);
  });

  await page.goto("/");
  // ... test actions

  // Attach console log to test report
  await testInfo.attach("console-log", {
    body: logs.join("\n"),
    contentType: "text/plain",
  });
});
```

## Anti-Patterns to Avoid

| Anti-Pattern               | Problem                    | Solution                    |
| -------------------------- | -------------------------- | --------------------------- |
| Ignoring console errors    | Bugs go unnoticed          | Check for errors in tests   |
| Too strict error checking  | Tests fail on minor issues | Allow known/expected errors |
| Not capturing stack traces | Hard to debug              | Include location info       |
| Checking only at end       | Miss errors during actions | Capture continuously        |

## Related References

- **Debugging**: See [debugging.md](debugging.md) for troubleshooting
- **Error Testing**: See [error-testing.md](error-testing.md) for error scenarios
