# Security Testing Basics

## Table of Contents

1. [XSS Prevention](#xss-prevention)
2. [CSRF Protection](#csrf-protection)
3. [Authentication Security](#authentication-security)
4. [Authorization Testing](#authorization-testing)
5. [Input Validation](#input-validation)
6. [Security Headers](#security-headers)

## XSS Prevention

### Test Reflected XSS

```typescript
test("input is properly escaped", async ({ page }) => {
  const xssPayloads = [
    '<script>alert("xss")</script>',
    '<img src="x" onerror="alert(1)">',
    '"><script>alert(1)</script>',
    "javascript:alert(1)",
    '<svg onload="alert(1)">',
  ];

  for (const payload of xssPayloads) {
    await page.goto(`/search?q=${encodeURIComponent(payload)}`);

    // Verify script didn't execute
    const alertTriggered = await page.evaluate(() => {
      return (window as any).__xssTriggered === true;
    });
    expect(alertTriggered).toBe(false);

    // Verify payload is escaped in HTML
    const content = await page.content();
    expect(content).not.toContain("<script>alert");
    expect(content).not.toContain("onerror=");
  }
});
```

### Test Stored XSS

```typescript
test("user content is sanitized", async ({ page }) => {
  await page.goto("/create-post");

  // Try to inject script via form
  await page.getByLabel("Content").fill('<script>alert("xss")</script>Hello');
  await page.getByRole("button", { name: "Submit" }).click();

  // View the post
  await page.goto("/posts/latest");

  // Script should not be in page
  const scripts = await page.locator("script").count();
  const pageContent = await page.content();

  // The script tag should be escaped or removed
  expect(pageContent).not.toContain("<script>alert");

  // Text should still be visible (just sanitized)
  await expect(page.getByText("Hello")).toBeVisible();
});
```

### Monitor for XSS Execution

```typescript
test("no XSS execution", async ({ page }) => {
  // Set up XSS detection
  await page.addInitScript(() => {
    (window as any).__xssDetected = false;

    // Override alert/confirm/prompt
    window.alert = () => {
      (window as any).__xssDetected = true;
    };
    window.confirm = () => {
      (window as any).__xssDetected = true;
      return false;
    };
    window.prompt = () => {
      (window as any).__xssDetected = true;
      return null;
    };
  });

  // Perform test actions
  await page.goto("/vulnerable-page");
  await page.getByLabel("Search").fill('"><img src=x onerror=alert(1)>');
  await page.getByLabel("Search").press("Enter");

  // Check if XSS triggered
  const xssDetected = await page.evaluate(() => (window as any).__xssDetected);
  expect(xssDetected).toBe(false);
});
```

## CSRF Protection

### Verify CSRF Token Present

```typescript
test("forms include CSRF token", async ({ page }) => {
  await page.goto("/settings");

  // Check form has CSRF token
  const csrfInput = page.locator(
    'input[name="_csrf"], input[name="csrf_token"]',
  );
  await expect(csrfInput).toBeAttached();

  const csrfValue = await csrfInput.getAttribute("value");
  expect(csrfValue).toBeTruthy();
  expect(csrfValue!.length).toBeGreaterThan(20);
});
```

### Test CSRF Token Validation

```typescript
test("rejects requests without CSRF token", async ({ page, request }) => {
  await page.goto("/settings");

  // Try to submit without CSRF token
  const response = await request.post("/api/settings", {
    data: { theme: "dark" },
    headers: {
      "Content-Type": "application/json",
    },
  });

  // Should be rejected
  expect(response.status()).toBe(403);
});

test("rejects requests with invalid CSRF token", async ({ page, request }) => {
  await page.goto("/settings");

  const response = await request.post("/api/settings", {
    data: { theme: "dark" },
    headers: {
      "X-CSRF-Token": "invalid-token",
    },
  });

  expect(response.status()).toBe(403);
});
```

### Test CSRF with Valid Token

```typescript
test("accepts requests with valid CSRF token", async ({ page }) => {
  await page.goto("/settings");

  // Get CSRF token from page
  const csrfToken = await page
    .locator('meta[name="csrf-token"]')
    .getAttribute("content");

  // Submit form normally
  await page.getByLabel("Theme").selectOption("dark");
  await page.getByRole("button", { name: "Save" }).click();

  // Should succeed
  await expect(page.getByText("Settings saved")).toBeVisible();
});
```

## Authentication Security

### Test Session Expiry

```typescript
test("session expires after timeout", async ({ page, context }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("user@example.com");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL("/dashboard");

  // Simulate time passing (if using clock mocking)
  await page.clock.fastForward("02:00:00"); // 2 hours

  // Try to access protected page
  await page.goto("/profile");

  // Should redirect to login
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByText("Session expired")).toBeVisible();
});
```

### Test Concurrent Sessions

```typescript
test("handles concurrent session limit", async ({ browser }) => {
  // Login from first browser
  const context1 = await browser.newContext();
  const page1 = await context1.newPage();

  await page1.goto("/login");
  await page1.getByLabel("Email").fill("user@example.com");
  await page1.getByLabel("Password").fill("password");
  await page1.getByRole("button", { name: "Sign in" }).click();
  await expect(page1).toHaveURL("/dashboard");

  // Login from second browser (same user)
  const context2 = await browser.newContext();
  const page2 = await context2.newPage();

  await page2.goto("/login");
  await page2.getByLabel("Email").fill("user@example.com");
  await page2.getByLabel("Password").fill("password");
  await page2.getByRole("button", { name: "Sign in" }).click();

  // First session should be invalidated (or warning shown)
  await page1.reload();
  await expect(
    page1.getByText(/session.*another device|logged out/i),
  ).toBeVisible();

  await context1.close();
  await context2.close();
});
```

### Test Password Reset Security

```typescript
test("password reset token is single-use", async ({ page, request }) => {
  // Request password reset
  await page.goto("/forgot-password");
  await page.getByLabel("Email").fill("user@example.com");
  await page.getByRole("button", { name: "Reset" }).click();

  // Get token (in test env, might be exposed or use email mock)
  const resetToken = "mock-reset-token";

  // Use token first time
  await page.goto(`/reset-password?token=${resetToken}`);
  await page.getByLabel("New Password").fill("NewPassword123");
  await page.getByRole("button", { name: "Reset" }).click();

  await expect(page.getByText("Password updated")).toBeVisible();

  // Try to use same token again
  await page.goto(`/reset-password?token=${resetToken}`);

  await expect(page.getByText("Invalid or expired token")).toBeVisible();
});
```

## Authorization Testing

### Test Unauthorized Access

```typescript
test.describe("authorization", () => {
  test("cannot access admin routes as user", async ({ browser }) => {
    const context = await browser.newContext({
      storageState: ".auth/user.json", // Regular user
    });
    const page = await context.newPage();

    // Try to access admin page
    await page.goto("/admin/users");

    // Should be denied
    await expect(page).not.toHaveURL("/admin/users");
    expect(
      (await page.getByText("Access denied").isVisible()) ||
        (await page.url()).includes("/login") ||
        (await page.url()).includes("/403"),
    ).toBe(true);

    await context.close();
  });

  test("cannot access other user's data", async ({ page }) => {
    // Logged in as user 1, try to access user 2's profile
    await page.goto("/users/other-user-id/settings");

    await expect(page.getByText("Access denied")).toBeVisible();
  });
});
```

### Test IDOR (Insecure Direct Object Reference)

```typescript
test("cannot access other user resources by changing ID", async ({
  page,
  request,
}) => {
  // Get current user's order
  await page.goto("/orders/my-order-123");
  await expect(page.getByText("Order #my-order-123")).toBeVisible();

  // Try to access another user's order
  const response = await request.get("/api/orders/other-user-order-456");

  // Should be forbidden
  expect(response.status()).toBe(403);
});
```

## Input Validation

### Test SQL Injection Prevention

```typescript
test("SQL injection is prevented", async ({ page }) => {
  const sqlPayloads = [
    "'; DROP TABLE users; --",
    "1' OR '1'='1",
    "1; DELETE FROM orders",
    "' UNION SELECT * FROM users --",
  ];

  for (const payload of sqlPayloads) {
    await page.goto("/search");
    await page.getByLabel("Search").fill(payload);
    await page.getByRole("button", { name: "Search" }).click();

    // Should not error (injection blocked/escaped)
    await expect(page.getByText("Error")).not.toBeVisible();

    // Should show no results or escaped text
    const hasError = await page
      .getByText(/database error|sql|syntax/i)
      .isVisible();
    expect(hasError).toBe(false);
  }
});
```

### Test Input Length Limits

```typescript
test("enforces input length limits", async ({ page }) => {
  await page.goto("/profile");

  // Try to submit very long input
  const longString = "a".repeat(10000);

  await page.getByLabel("Bio").fill(longString);
  await page.getByRole("button", { name: "Save" }).click();

  // Should show validation error or truncate
  const bioValue = await page.getByLabel("Bio").inputValue();
  expect(bioValue.length).toBeLessThanOrEqual(500); // Expected max
});
```

## Security Headers

### Verify Security Headers

```typescript
test("response includes security headers", async ({ page }) => {
  const response = await page.goto("/");

  const headers = response!.headers();

  // Content Security Policy
  expect(headers["content-security-policy"]).toBeTruthy();

  // Prevent clickjacking
  expect(headers["x-frame-options"]).toMatch(/DENY|SAMEORIGIN/);

  // Prevent MIME type sniffing
  expect(headers["x-content-type-options"]).toBe("nosniff");

  // XSS Protection (legacy but good to have)
  expect(headers["x-xss-protection"]).toBeTruthy();

  // HTTPS enforcement
  if (!page.url().includes("localhost")) {
    expect(headers["strict-transport-security"]).toBeTruthy();
  }
});
```

### Test CSP Violations

```typescript
test("CSP blocks inline scripts", async ({ page }) => {
  const cspViolations: string[] = [];

  // Listen for CSP violations via console
  page.on("console", (msg) => {
    if (msg.text().includes("Content Security Policy")) {
      cspViolations.push(msg.text());
    }
  });

  await page.goto("/");

  // Try to inject inline script - CSP should block it
  await page.evaluate(() => {
    const script = document.createElement("script");
    script.textContent = 'console.log("injected")';
    document.body.appendChild(script);
  });

  expect(cspViolations.length).toBeGreaterThan(0);
});
```

> **For comprehensive console monitoring** (fixtures, allowed patterns, fail on errors), see [console-errors.md](../debugging/console-errors.md).

## Anti-Patterns to Avoid

| Anti-Pattern               | Problem               | Solution                      |
| -------------------------- | --------------------- | ----------------------------- |
| Testing only happy path    | Misses security holes | Test malicious inputs         |
| Hardcoded test credentials | Security risk         | Use environment variables     |
| Skipping auth tests in dev | Bugs reach production | Test auth in all environments |
| Not testing authorization  | Access control bugs   | Test all role combinations    |

## Related References

- **Authentication**: See [fixtures-hooks.md](../core/fixtures-hooks.md) for auth fixtures
- **Multi-User**: See [multi-user.md](../advanced/multi-user.md) for role-based testing
- **Error Testing**: See [error-testing.md](../debugging/error-testing.md) for validation testing
