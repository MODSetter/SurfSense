# Complex Authentication Flow Patterns

## Table of Contents

1. [Email Verification Flows](#email-verification-flows)
2. [Password Reset](#password-reset)
3. [Session Timeout](#session-timeout)
4. [Remember Me Persistence](#remember-me-persistence)
5. [Logout Patterns](#logout-patterns)
6. [Tips](#tips)
7. [Related](#related)

> **When to use**: Testing email verification, password reset, session timeout/expiration, or remember-me functionality. For basic auth setup (storage state, OAuth mocking, MFA, role-based access), see [authentication.md](authentication.md).

---

## Email Verification Flows

### Capturing Verification Tokens

Intercept API responses to capture verification tokens for testing:

```typescript
test('completes registration with email verification', async ({ page }) => {
  let capturedToken = '';

  await page.route('**/api/auth/register', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    capturedToken = body.verificationToken;
    await route.fulfill({ response });
  });

  await page.goto('/register');
  await page.getByLabel('Name').fill('New User');
  await page.getByLabel('Email').fill('newuser@test.com');
  await page.getByLabel('Password', { exact: true }).fill('SecurePass!');
  await page.getByLabel('Confirm password').fill('SecurePass!');
  await page.getByRole('button', { name: 'Create account' }).click();

  await expect(page.getByText('Check your inbox')).toBeVisible();

  expect(capturedToken).toBeTruthy();
  await page.goto(`/verify?token=${capturedToken}`);

  await expect(page.getByText('Email confirmed')).toBeVisible();
});
```

### Fully Mocked Verification

```typescript
test('verifies email with mocked endpoints', async ({ page }) => {
  const mockToken = 'test-verification-abc123';

  await page.route('**/api/auth/register', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Verification sent', verificationToken: mockToken }),
    });
  });

  await page.route(`**/api/auth/verify?token=${mockToken}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ verified: true }),
    });
  });

  await page.goto('/register');
  await page.getByLabel('Email').fill('test@example.com');
  await page.getByLabel('Password', { exact: true }).fill('Password123!');
  await page.getByRole('button', { name: 'Sign up' }).click();

  await expect(page.getByText('Check your inbox')).toBeVisible();

  await page.goto(`/verify?token=${mockToken}`);
  await expect(page.getByText('Email confirmed')).toBeVisible();
});
```

---

## Password Reset

### Complete Reset Flow

```typescript
test('resets password through email link', async ({ page }) => {
  let resetToken = '';

  await page.route('**/api/auth/forgot-password', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    resetToken = body.resetToken;
    await route.fulfill({ response });
  });

  await page.goto('/forgot-password');
  await page.getByLabel('Email').fill('user@test.com');
  await page.getByRole('button', { name: 'Send link' }).click();

  await expect(page.getByText('Reset email sent')).toBeVisible();

  expect(resetToken).toBeTruthy();
  await page.goto(`/reset-password?token=${resetToken}`);

  await page.getByLabel('New password', { exact: true }).fill('NewPassword456!');
  await page.getByLabel('Confirm password').fill('NewPassword456!');
  await page.getByRole('button', { name: 'Update password' }).click();

  await expect(page.getByText('Password updated')).toBeVisible();
});
```

### Expired Token Handling

```typescript
test('shows error for expired reset token', async ({ page }) => {
  await page.goto('/reset-password?token=expired-token');

  await page.getByLabel('New password', { exact: true }).fill('NewPass!');
  await page.getByLabel('Confirm password').fill('NewPass!');
  await page.getByRole('button', { name: 'Update password' }).click();

  await expect(page.getByRole('alert')).toContainText(/expired|invalid/i);
});
```

### Password Strength Validation

```typescript
test('enforces password requirements on reset', async ({ page }) => {
  await page.goto('/reset-password?token=valid-token');

  await page.getByLabel('New password', { exact: true }).fill('weak');
  await page.getByLabel('Confirm password').fill('weak');
  await page.getByRole('button', { name: 'Update password' }).click();

  await expect(page.getByText(/at least 8 characters/i)).toBeVisible();
});
```

---

## Session Timeout

### Detecting Expired Sessions

```typescript
test('redirects to signin after session expires', async ({ page, context }) => {
  await page.goto('/signin');
  await page.getByLabel('Email').fill('user@test.com');
  await page.getByLabel('Password').fill('Password!');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL('/home');

  const cookies = await context.cookies();
  const sessionCookie = cookies.find((c) => c.name.includes('session'));

  if (sessionCookie) {
    await context.clearCookies({ name: sessionCookie.name });
  }

  await page.goto('/profile');
  await expect(page).toHaveURL(/\/signin/);
  await expect(page.getByText(/session.*expired|sign in again/i)).toBeVisible();
});
```

### Session Extension Warning

```typescript
test('shows warning before session expires', async ({ page }) => {
  await page.route('**/api/auth/session', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ valid: true, expiresIn: 60 }),
    });
  });

  await page.goto('/home');

  await expect(page.getByText(/session.*expir/i)).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole('button', { name: /extend|stay signed in/i })).toBeVisible();
});
```

### Session Extension Action

```typescript
test('extends session when user clicks extend', async ({ page }) => {
  let sessionExtended = false;

  await page.route('**/api/auth/session', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ valid: true, expiresIn: 60 }),
    });
  });

  await page.route('**/api/auth/refresh', async (route) => {
    sessionExtended = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ valid: true, expiresIn: 3600 }),
    });
  });

  await page.goto('/home');

  await expect(page.getByRole('button', { name: /extend|stay signed in/i })).toBeVisible({
    timeout: 10000,
  });
  await page.getByRole('button', { name: /extend|stay signed in/i }).click();

  expect(sessionExtended).toBe(true);
  await expect(page.getByText(/session.*expir/i)).not.toBeVisible();
});
```

---

## Remember Me Persistence

### Persistent Session

```typescript
test('persists session with remember me enabled', async ({ browser }) => {
  const ctx1 = await browser.newContext();
  const page1 = await ctx1.newPage();

  await page1.goto('/signin');
  await page1.getByLabel('Email').fill('user@test.com');
  await page1.getByLabel('Password').fill('Password!');
  await page1.getByLabel('Keep me signed in').check();
  await page1.getByRole('button', { name: 'Sign in' }).click();

  await expect(page1).toHaveURL('/home');

  const state = await ctx1.storageState();
  await ctx1.close();

  const ctx2 = await browser.newContext({ storageState: state });
  const page2 = await ctx2.newPage();

  await page2.goto('/home');
  await expect(page2).toHaveURL('/home');
  await expect(page2.getByText('Welcome')).toBeVisible();

  await ctx2.close();
});
```

### Session-Only Login

```typescript
test('session-only login does not persist across browser restarts', async ({ browser }) => {
  const ctx1 = await browser.newContext();
  const page1 = await ctx1.newPage();

  await page1.goto('/signin');
  await page1.getByLabel('Email').fill('user@test.com');
  await page1.getByLabel('Password').fill('Password!');
  // Leave "Remember me" unchecked
  await expect(page1.getByLabel('Keep me signed in')).not.toBeChecked();
  await page1.getByRole('button', { name: 'Sign in' }).click();

  await expect(page1).toHaveURL('/home');

  // Only keep persistent cookies (filter out session cookies)
  const cookies = await ctx1.cookies();
  await ctx1.close();

  const persistentCookies = cookies.filter((c) => c.expires > 0);
  const ctx2 = await browser.newContext();
  await ctx2.addCookies(persistentCookies);
  const page2 = await ctx2.newPage();

  await page2.goto('/home');

  // Should redirect to login since session was not persisted
  await expect(page2).toHaveURL(/\/signin/);

  await ctx2.close();
});
```

---

## Logout Patterns

### Standard Logout with Session Cleanup

```typescript
test.use({ storageState: '.auth/user.json' });

test('logs out and clears session', async ({ page, context }) => {
  await page.goto('/home');

  await page.getByRole('button', { name: /account|menu/i }).click();
  await page.getByRole('menuitem', { name: 'Sign out' }).click();

  await expect(page).toHaveURL('/signin');

  const cookies = await context.cookies();
  const sessionCookies = cookies.filter((c) => c.name.includes('session') || c.name.includes('token'));
  expect(sessionCookies).toHaveLength(0);

  await page.goto('/home');
  await expect(page).toHaveURL(/\/signin/);
});
```

### Logout from All Devices

```typescript
test('logs out from all devices', async ({ page }) => {
  let logoutAllCalled = false;

  await page.route('**/api/auth/logout-all', async (route) => {
    logoutAllCalled = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Logged out everywhere' }),
    });
  });

  await page.goto('/settings/security');

  await page.getByRole('button', { name: 'Sign out everywhere' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Confirm' }).click();

  expect(logoutAllCalled).toBe(true);
  await expect(page).toHaveURL(/\/signin/);
});
```

---

## Tips

1. **Configure shorter session timeouts in test environments** — Enables testing timeout behavior without slow tests
2. **Test token expiration edge cases** — Expired tokens, invalid tokens, already-used tokens
3. **Verify cleanup on logout** — Check both cookies and localStorage are cleared
4. **Test the full flow end-to-end** — Password reset should verify login with new password works

---

## Related

- [authentication.md](authentication.md) — Storage state, OAuth mocking, MFA, role-based access, API login
- [fixtures-hooks.md](../core/fixtures-hooks.md) — Creating auth fixtures
- [third-party.md](./third-party.md) — Mocking external auth providers
