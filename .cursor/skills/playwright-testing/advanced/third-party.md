# Third-Party Service Mocking

## Table of Contents

1. [OAuth/SSO Mocking](#oauthsso-mocking)
2. [Payment Gateway Mocking](#payment-gateway-mocking)
3. [Email Verification](#email-verification)
4. [SMS Verification](#sms-verification)
5. [Analytics & Tracking](#analytics--tracking)

## OAuth/SSO Mocking

### Mock Google OAuth

```typescript
test("Google OAuth login", async ({ page }) => {
  // Mock the OAuth callback
  await page.route("**/auth/google/callback**", (route) => {
    const url = new URL(route.request().url());
    // Simulate successful OAuth by redirecting with token
    route.fulfill({
      status: 302,
      headers: {
        Location: "/dashboard?token=mock-jwt-token",
      },
    });
  });

  // Mock the token verification endpoint
  await page.route("**/api/auth/verify", (route) =>
    route.fulfill({
      json: {
        valid: true,
        user: {
          id: "123",
          email: "test@gmail.com",
          name: "Test User",
        },
      },
    }),
  );

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in with Google" }).click();

  await expect(page.getByText("Welcome, Test User")).toBeVisible();
});
```

### OAuth Fixture

```typescript
// fixtures/oauth.fixture.ts
type OAuthProvider = "google" | "github" | "microsoft";

type OAuthUser = {
  id: string;
  email: string;
  name: string;
  avatar?: string;
};

type OAuthFixtures = {
  mockOAuth: (provider: OAuthProvider, user: OAuthUser) => Promise<void>;
};

export const test = base.extend<OAuthFixtures>({
  mockOAuth: async ({ page }, use) => {
    await use(async (provider, user) => {
      // Mock callback redirect
      await page.route(`**/auth/${provider}/callback**`, (route) =>
        route.fulfill({
          status: 302,
          headers: { Location: `/auth/success?provider=${provider}` },
        }),
      );

      // Mock session/user endpoint
      await page.route("**/api/auth/session", (route) =>
        route.fulfill({
          json: { user, provider, authenticated: true },
        }),
      );

      // Mock user info endpoint
      await page.route("**/api/me", (route) => route.fulfill({ json: user }));
    });
  },
});

// Usage
test("login with GitHub", async ({ page, mockOAuth }) => {
  await mockOAuth("github", {
    id: "gh-123",
    email: "dev@github.com",
    name: "GitHub User",
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in with GitHub" }).click();

  await expect(page.getByText("Welcome, GitHub User")).toBeVisible();
});
```

### Mock SAML SSO

```typescript
test("SAML SSO login", async ({ page }) => {
  // Mock SAML assertion consumer service
  await page.route("**/saml/acs", async (route) => {
    route.fulfill({
      status: 302,
      headers: {
        Location: "/dashboard",
        "Set-Cookie": "session=mock-saml-session; Path=/; HttpOnly",
      },
    });
  });

  // Mock session validation
  await page.route("**/api/session", (route) =>
    route.fulfill({
      json: {
        user: { email: "user@company.com", name: "SSO User" },
        provider: "saml",
      },
    }),
  );

  await page.goto("/login");
  await page.getByRole("button", { name: "SSO Login" }).click();

  await expect(page).toHaveURL("/dashboard");
});
```

## Payment Gateway Mocking

### Mock Stripe

```typescript
test("Stripe checkout", async ({ page }) => {
  // Mock Stripe.js
  await page.addInitScript(() => {
    (window as any).Stripe = () => ({
      elements: () => ({
        create: () => ({
          mount: () => {},
          on: () => {},
          destroy: () => {},
        }),
      }),
      confirmCardPayment: async () => ({
        paymentIntent: { status: "succeeded", id: "pi_mock_123" },
      }),
      createPaymentMethod: async () => ({
        paymentMethod: { id: "pm_mock_123" },
      }),
    });
  });

  // Mock backend payment endpoint
  await page.route("**/api/create-payment-intent", (route) =>
    route.fulfill({
      json: { clientSecret: "pi_mock_123_secret_mock" },
    }),
  );

  await page.route("**/api/confirm-payment", (route) =>
    route.fulfill({
      json: { success: true, orderId: "order-123" },
    }),
  );

  await page.goto("/checkout");
  await page.getByRole("button", { name: "Pay $99.99" }).click();

  await expect(page.getByText("Payment successful")).toBeVisible();
});
```

### Mock PayPal

```typescript
test("PayPal checkout", async ({ page }) => {
  // Mock PayPal SDK
  await page.addInitScript(() => {
    (window as any).paypal = {
      Buttons: () => ({
        render: () => Promise.resolve(),
        isEligible: () => true,
      }),
      FUNDING: { PAYPAL: "paypal", CARD: "card" },
    };
  });

  // Mock PayPal order creation
  await page.route("**/api/paypal/create-order", (route) =>
    route.fulfill({
      json: { orderId: "PAYPAL-ORDER-123" },
    }),
  );

  // Mock PayPal capture
  await page.route("**/api/paypal/capture", (route) =>
    route.fulfill({
      json: { success: true, transactionId: "TXN-123" },
    }),
  );

  await page.goto("/checkout");

  // Simulate PayPal approval callback
  await page.evaluate(() => {
    (window as any).onPayPalApprove?.({ orderID: "PAYPAL-ORDER-123" });
  });

  await expect(page.getByText("Order confirmed")).toBeVisible();
});
```

### Payment Fixture

```typescript
// fixtures/payment.fixture.ts
type PaymentFixtures = {
  mockStripe: (options?: { failPayment?: boolean }) => Promise<void>;
};

export const test = base.extend<PaymentFixtures>({
  mockStripe: async ({ page }, use) => {
    await use(async (options = {}) => {
      await page.addInitScript(
        ([shouldFail]) => {
          (window as any).Stripe = () => ({
            elements: () => ({
              create: () => ({
                mount: () => {},
                on: (event: string, handler: Function) => {
                  if (event === "ready") setTimeout(handler, 100);
                },
                destroy: () => {},
              }),
            }),
            confirmCardPayment: async () => {
              if (shouldFail) {
                return { error: { message: "Card declined" } };
              }
              return { paymentIntent: { status: "succeeded" } };
            },
          });
        },
        [options.failPayment],
      );
    });
  },
});

// Usage
test("handles declined card", async ({ page, mockStripe }) => {
  await mockStripe({ failPayment: true });

  await page.goto("/checkout");
  await page.getByRole("button", { name: "Pay" }).click();

  await expect(page.getByText("Card declined")).toBeVisible();
});
```

## Email Verification

### Mock Email API

```typescript
test("email verification flow", async ({ page, request }) => {
  let verificationToken: string;

  // Capture the verification email
  await page.route("**/api/send-verification", async (route) => {
    const body = route.request().postDataJSON();
    verificationToken = `mock-token-${Date.now()}`;

    // Don't actually send email, just store token
    route.fulfill({
      json: { sent: true, messageId: "msg-123" },
    });
  });

  // Mock token verification
  await page.route("**/api/verify-email**", (route) => {
    const url = new URL(route.request().url());
    const token = url.searchParams.get("token");

    if (token === verificationToken) {
      route.fulfill({ json: { verified: true } });
    } else {
      route.fulfill({ status: 400, json: { error: "Invalid token" } });
    }
  });

  await page.goto("/signup");
  await page.getByLabel("Email").fill("test@example.com");
  await page.getByRole("button", { name: "Sign Up" }).click();

  await expect(page.getByText("Check your email")).toBeVisible();

  // Simulate clicking email link
  await page.goto(`/verify?token=${verificationToken}`);

  await expect(page.getByText("Email verified")).toBeVisible();
});
```

### Use Mailinator/Temp Mail

```typescript
// fixtures/email.fixture.ts
type EmailFixtures = {
  getVerificationEmail: (inbox: string) => Promise<{ link: string }>;
};

export const test = base.extend<EmailFixtures>({
  getVerificationEmail: async ({ request }, use) => {
    await use(async (inbox) => {
      // Poll Mailinator API for new email
      const response = await request.get(
        `https://api.mailinator.com/v2/domains/public/inboxes/${inbox}`,
        {
          headers: {
            Authorization: `Bearer ${process.env.MAILINATOR_API_KEY}`,
          },
        },
      );

      const messages = await response.json();
      const latest = messages.msgs[0];

      // Get full message
      const msgResponse = await request.get(
        `https://api.mailinator.com/v2/domains/public/inboxes/${inbox}/messages/${latest.id}`,
        {
          headers: {
            Authorization: `Bearer ${process.env.MAILINATOR_API_KEY}`,
          },
        },
      );

      const message = await msgResponse.json();

      // Extract verification link from HTML
      const linkMatch = message.parts[0].body.match(
        /href="([^"]*verify[^"]*)"/,
      );
      return { link: linkMatch?.[1] || "" };
    });
  },
});
```

## SMS Verification

### Mock SMS API

```typescript
test("SMS verification", async ({ page }) => {
  let smsCode: string;

  // Capture SMS send
  await page.route("**/api/send-sms", (route) => {
    smsCode = Math.random().toString().slice(2, 8); // 6-digit code

    route.fulfill({
      json: { sent: true, messageId: "sms-123" },
    });
  });

  // Mock code verification
  await page.route("**/api/verify-sms", (route) => {
    const body = route.request().postDataJSON();

    if (body.code === smsCode) {
      route.fulfill({ json: { verified: true } });
    } else {
      route.fulfill({ status: 400, json: { error: "Invalid code" } });
    }
  });

  await page.goto("/verify-phone");
  await page.getByLabel("Phone").fill("+1234567890");
  await page.getByRole("button", { name: "Send Code" }).click();

  // Enter the code
  await page.getByLabel("Verification Code").fill(smsCode);
  await page.getByRole("button", { name: "Verify" }).click();

  await expect(page.getByText("Phone verified")).toBeVisible();
});
```

## Analytics & Tracking

### Block Analytics in Tests

```typescript
test.beforeEach(async ({ page }) => {
  // Block all analytics/tracking
  await page.route(
    /google-analytics|googletagmanager|facebook|hotjar|segment|mixpanel|amplitude/,
    (route) => route.abort(),
  );
});
```

### Mock Analytics for Verification

```typescript
test("tracks purchase event", async ({ page }) => {
  const analyticsEvents: any[] = [];

  // Capture analytics calls
  await page.route("**/api/analytics/**", (route) => {
    analyticsEvents.push(route.request().postDataJSON());
    route.fulfill({ status: 200 });
  });

  // Mock analytics SDK
  await page.addInitScript(() => {
    (window as any).analytics = {
      track: (event: string, props: any) => {
        fetch("/api/analytics/track", {
          method: "POST",
          body: JSON.stringify({ event, props }),
        });
      },
    };
  });

  await page.goto("/checkout");
  await page.getByRole("button", { name: "Complete Purchase" }).click();

  // Verify analytics event was sent
  expect(analyticsEvents).toContainEqual(
    expect.objectContaining({
      event: "Purchase Completed",
      props: expect.objectContaining({ amount: expect.any(Number) }),
    }),
  );
});
```

## Anti-Patterns to Avoid

| Anti-Pattern              | Problem                        | Solution                |
| ------------------------- | ------------------------------ | ----------------------- |
| Using real OAuth in tests | Slow, needs credentials, flaky | Mock OAuth endpoints    |
| Real payment processing   | Charges real money, slow       | Use test mode or mock   |
| Waiting for real emails   | Very slow, unreliable          | Mock email API          |
| Not mocking analytics     | Pollutes analytics data        | Block or mock analytics |

## Related References

- **Network Mocking**: See [network-advanced.md](network-advanced.md) for route patterns
- **Authentication**: See [fixtures-hooks.md](../core/fixtures-hooks.md) for auth patterns
