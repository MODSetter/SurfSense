# Error & Edge Case Testing

## Table of Contents

1. [Error Boundaries](#error-boundaries)
2. [Network Failures](#network-failures)
3. [Offline Testing](#offline-testing)
4. [Loading States](#loading-states)
5. [Form Validation](#form-validation)

## Error Boundaries

### Test Component Errors

```typescript
test("error boundary catches component error", async ({ page }) => {
  // Trigger error via mock
  await page.route("**/api/user", (route) => {
    route.fulfill({
      json: null, // Will cause component to throw
    });
  });

  await page.goto("/profile");

  // Error boundary should render fallback
  await expect(page.getByText("Something went wrong")).toBeVisible();
  await expect(page.getByRole("button", { name: "Try Again" })).toBeVisible();
});
```

### Test Error Recovery

```typescript
test("recover from error state", async ({ page }) => {
  let requestCount = 0;

  await page.route("**/api/data", (route) => {
    requestCount++;
    if (requestCount === 1) {
      return route.fulfill({ status: 500 });
    }
    return route.fulfill({
      json: { data: "success" },
    });
  });

  await page.goto("/dashboard");

  // Error state
  await expect(page.getByText("Failed to load")).toBeVisible();

  // Retry
  await page.getByRole("button", { name: "Retry" }).click();

  // Success state
  await expect(page.getByText("success")).toBeVisible();
});
```

### Test JavaScript Errors

```typescript
test("handles runtime error gracefully", async ({ page }) => {
  const errors: string[] = [];

  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await page.goto("/buggy-page");

  // App should still be functional despite error
  await expect(page.getByRole("navigation")).toBeVisible();

  // Error was logged
  expect(errors.length).toBeGreaterThan(0);
});
```

## Network Failures

### Test API Errors

```typescript
test.describe("API error handling", () => {
  const errorCodes = [400, 401, 403, 404, 500, 502, 503];

  for (const status of errorCodes) {
    test(`handles ${status} error`, async ({ page }) => {
      await page.route("**/api/data", (route) =>
        route.fulfill({
          status,
          json: { error: `Error ${status}` },
        }),
      );

      await page.goto("/dashboard");

      // Appropriate error message shown
      await expect(page.getByRole("alert")).toBeVisible();
    });
  }
});
```

### Test Timeout

```typescript
test("handles request timeout", async ({ page }) => {
  await page.route("**/api/slow", async (route) => {
    // Never respond - simulates timeout
    await new Promise(() => {});
  });

  await page.goto("/slow-page");

  // Should show timeout message (app should have its own timeout)
  await expect(page.getByText("Request timed out")).toBeVisible({
    timeout: 15000,
  });
});
```

### Test Connection Reset

```typescript
test("handles connection failure", async ({ page }) => {
  await page.route("**/api/data", (route) => {
    route.abort("connectionfailed");
  });

  await page.goto("/dashboard");

  await expect(page.getByText("Connection failed")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});
```

### Test Mid-Request Failure

```typescript
test("handles failure during request", async ({ page }) => {
  let requestStarted = false;

  await page.route("**/api/upload", async (route) => {
    requestStarted = true;
    // Abort after small delay (mid-request)
    await new Promise((resolve) => setTimeout(resolve, 500));
    route.abort("failed");
  });

  await page.goto("/upload");
  await page.getByLabel("File").setInputFiles("./fixtures/large-file.pdf");
  await page.getByRole("button", { name: "Upload" }).click();

  // Should show failure, not hang
  await expect(page.getByText("Upload failed")).toBeVisible();
  expect(requestStarted).toBe(true);
});
```

## Offline Testing

This section covers **unexpected network failures** and error recovery. For **offline-first apps (PWAs)** with service workers, caching, and background sync, see [service-workers.md](service-workers.md#offline-testing).

### Go Offline During Session

```typescript
test("handles going offline", async ({ page, context }) => {
  await page.goto("/dashboard");
  await expect(page.getByTestId("data")).toBeVisible();

  // Go offline unexpectedly
  await context.setOffline(true);

  // Try to refresh data
  await page.getByRole("button", { name: "Refresh" }).click();

  // Should show offline indicator
  await expect(page.getByText("You're offline")).toBeVisible();

  // Go back online
  await context.setOffline(false);

  // Should recover
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByText("You're offline")).toBeHidden();
});
```

### Test Network Recovery

```typescript
test("recovers gracefully when connection returns", async ({
  page,
  context,
}) => {
  await page.goto("/dashboard");

  // Simulate connection drop
  await context.setOffline(true);

  // App should show degraded state
  await expect(page.getByRole("alert")).toContainText(/offline|connection/i);

  // Connection restored
  await context.setOffline(false);

  // Retry should work
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByTestId("data")).toBeVisible();
});
```

## Loading States

### Test Skeleton Loaders

```typescript
test("shows skeleton during load", async ({ page }) => {
  // Add delay to API response
  await page.route("**/api/posts", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    route.fulfill({
      json: [{ id: 1, title: "Post 1" }],
    });
  });

  await page.goto("/posts");

  // Skeleton should appear immediately
  await expect(page.getByTestId("skeleton")).toBeVisible();

  // Then content replaces skeleton
  await expect(page.getByText("Post 1")).toBeVisible();
  await expect(page.getByTestId("skeleton")).toBeHidden();
});
```

### Test Loading Indicators

```typescript
test("shows loading state for actions", async ({ page }) => {
  await page.route("**/api/save", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    route.fulfill({ json: { success: true } });
  });

  await page.goto("/editor");
  await page.getByLabel("Content").fill("New content");

  const saveButton = page.getByRole("button", { name: "Save" });
  await saveButton.click();

  // Button should show loading state
  await expect(saveButton).toBeDisabled();
  await expect(page.getByTestId("spinner")).toBeVisible();

  // Then success state
  await expect(saveButton).toBeEnabled();
  await expect(page.getByText("Saved")).toBeVisible();
});
```

### Test Empty States

```typescript
test("shows empty state when no data", async ({ page }) => {
  await page.route("**/api/items", (route) => route.fulfill({ json: [] }));

  await page.goto("/items");

  await expect(page.getByText("No items yet")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Create First Item" }),
  ).toBeVisible();
});
```

## Form Validation

### Test Client-Side Validation

```typescript
test("validates required fields", async ({ page }) => {
  await page.goto("/signup");

  // Submit empty form
  await page.getByRole("button", { name: "Sign Up" }).click();

  // Should show validation errors
  await expect(page.getByText("Email is required")).toBeVisible();
  await expect(page.getByText("Password is required")).toBeVisible();

  // Form should not submit
  await expect(page).toHaveURL("/signup");
});
```

### Test Format Validation

```typescript
test("validates email format", async ({ page }) => {
  await page.goto("/signup");

  await page.getByLabel("Email").fill("invalid-email");
  await page.getByLabel("Email").blur();

  await expect(page.getByText("Invalid email address")).toBeVisible();

  // Fix the error
  await page.getByLabel("Email").fill("valid@email.com");
  await page.getByLabel("Email").blur();

  await expect(page.getByText("Invalid email address")).toBeHidden();
});
```

### Test Server-Side Validation

```typescript
test("handles server validation errors", async ({ page }) => {
  await page.route("**/api/register", (route) =>
    route.fulfill({
      status: 422,
      json: {
        errors: {
          email: "Email already exists",
          username: "Username is taken",
        },
      },
    }),
  );

  await page.goto("/signup");
  await page.getByLabel("Email").fill("taken@email.com");
  await page.getByLabel("Username").fill("takenuser");
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign Up" }).click();

  // Server errors should display
  await expect(page.getByText("Email already exists")).toBeVisible();
  await expect(page.getByText("Username is taken")).toBeVisible();
});
```

## Anti-Patterns to Avoid

| Anti-Pattern             | Problem                        | Solution                               |
| ------------------------ | ------------------------------ | -------------------------------------- |
| Only testing happy path  | Misses error handling bugs     | Test all error scenarios               |
| No network failure tests | App crashes on poor connection | Test offline/slow/failed requests      |
| Skipping loading states  | Janky UX not caught            | Assert loading UI appears              |
| Ignoring validation      | Form bugs slip through         | Test both client and server validation |

## Related References

- **Network Mocking**: See [network-advanced.md](../advanced/network-advanced.md) for mock patterns
- **Assertions**: See [assertions-waiting.md](../core/assertions-waiting.md) for error assertions
