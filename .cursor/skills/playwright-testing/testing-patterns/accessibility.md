# Accessibility Testing

## Table of Contents

1. [Axe-Core Integration](#axe-core-integration)
2. [Keyboard Navigation](#keyboard-navigation)
3. [ARIA Validation](#aria-validation)
4. [Focus Management](#focus-management)
5. [Color & Contrast](#color--contrast)

## Axe-Core Integration

### Setup

```bash
npm install -D @axe-core/playwright
```

### Basic A11y Test

```typescript
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("homepage should have no a11y violations", async ({ page }) => {
  await page.goto("/");

  const results = await new AxeBuilder({ page }).analyze();

  expect(results.violations).toEqual([]);
});
```

### Scoped Analysis

```typescript
test("form accessibility", async ({ page }) => {
  await page.goto("/contact");

  // Analyze only the form
  const results = await new AxeBuilder({ page })
    .include("#contact-form")
    .analyze();

  expect(results.violations).toEqual([]);
});

test("ignore known issues", async ({ page }) => {
  await page.goto("/legacy-page");

  const results = await new AxeBuilder({ page })
    .exclude(".legacy-widget") // Skip legacy component
    .disableRules(["color-contrast"]) // Disable specific rule
    .analyze();

  expect(results.violations).toEqual([]);
});
```

### A11y Fixture

```typescript
// fixtures/a11y.fixture.ts
import { test as base } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

type A11yFixtures = {
  makeAxeBuilder: () => AxeBuilder;
};

export const test = base.extend<A11yFixtures>({
  makeAxeBuilder: async ({ page }, use) => {
    await use(() =>
      new AxeBuilder({ page }).withTags([
        "wcag2a",
        "wcag2aa",
        "wcag21a",
        "wcag21aa",
      ]),
    );
  },
});

// Usage
test("dashboard a11y", async ({ page, makeAxeBuilder }) => {
  await page.goto("/dashboard");
  const results = await makeAxeBuilder().analyze();
  expect(results.violations).toEqual([]);
});
```

### Detailed Violation Reporting

```typescript
test("report a11y issues", async ({ page }) => {
  await page.goto("/");

  const results = await new AxeBuilder({ page }).analyze();

  // Custom failure message with details
  const violations = results.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    description: v.description,
    nodes: v.nodes.map((n) => n.html),
  }));

  expect(violations, JSON.stringify(violations, null, 2)).toHaveLength(0);
});
```

## Keyboard Navigation

### Tab Order Testing

```typescript
test("correct tab order in form", async ({ page }) => {
  await page.goto("/signup");

  // Start from the beginning
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Email")).toBeFocused();

  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password")).toBeFocused();

  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Sign up" })).toBeFocused();
});
```

### Keyboard-Only Interaction

```typescript
test("complete flow with keyboard only", async ({ page }) => {
  await page.goto("/products");

  // Navigate to product with keyboard
  await page.keyboard.press("Tab"); // Skip to main content
  await page.keyboard.press("Tab"); // First product
  await page.keyboard.press("Enter"); // Open product

  await expect(page).toHaveURL(/\/products\/\d+/);

  // Add to cart with keyboard
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab"); // Navigate to "Add to Cart"
  await page.keyboard.press("Enter");

  await expect(page.getByRole("alert")).toContainText("Added to cart");
});
```

### Skip Links

```typescript
test("skip link works", async ({ page }) => {
  await page.goto("/");

  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: /skip to main/i });
  await expect(skipLink).toBeFocused();

  await page.keyboard.press("Enter");

  // Focus should move to main content
  await expect(page.getByRole("main")).toBeFocused();
});
```

### Escape Key Handling

```typescript
test("escape closes modal", async ({ page }) => {
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Settings" }).click();

  const modal = page.getByRole("dialog");
  await expect(modal).toBeVisible();

  await page.keyboard.press("Escape");

  await expect(modal).toBeHidden();
  // Focus should return to trigger
  await expect(page.getByRole("button", { name: "Settings" })).toBeFocused();
});
```

## ARIA Validation

### Role Verification

```typescript
test("correct ARIA roles", async ({ page }) => {
  await page.goto("/dashboard");

  // Verify landmark roles
  await expect(page.getByRole("navigation")).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("contentinfo")).toBeVisible(); // footer

  // Verify interactive roles
  await expect(page.getByRole("button", { name: "Menu" })).toBeVisible();
  await expect(page.getByRole("search")).toBeVisible();
});
```

### ARIA States

```typescript
test("aria-expanded updates correctly", async ({ page }) => {
  await page.goto("/faq");

  const accordion = page.getByRole("button", { name: "Shipping" });

  // Initially collapsed
  await expect(accordion).toHaveAttribute("aria-expanded", "false");

  await accordion.click();

  // Now expanded
  await expect(accordion).toHaveAttribute("aria-expanded", "true");

  // Content is visible
  const panel = page.getByRole("region", { name: "Shipping" });
  await expect(panel).toBeVisible();
});
```

### Live Regions

```typescript
test("live region announces updates", async ({ page }) => {
  await page.goto("/checkout");

  // Find live region
  const liveRegion = page.locator('[aria-live="polite"]');

  await page.getByLabel("Quantity").fill("3");

  // Live region should update with new total
  await expect(liveRegion).toContainText("Total: $29.97");
});
```

## Focus Management

### Focus Trap in Modal

```typescript
test("focus trapped in modal", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Open Modal" }).click();

  const modal = page.getByRole("dialog");
  await expect(modal).toBeVisible();

  // Get all focusable elements in modal
  const focusableElements = modal.locator(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
  );
  const count = await focusableElements.count();

  // Tab through all elements, should stay in modal
  for (let i = 0; i < count + 1; i++) {
    await page.keyboard.press("Tab");
    const focused = page.locator(":focus");
    await expect(modal).toContainText((await focused.textContent()) || "");
  }
});
```

### Focus Restoration

```typescript
test("focus returns after modal close", async ({ page }) => {
  await page.goto("/");

  const trigger = page.getByRole("button", { name: "Delete Item" });
  await trigger.click();

  await page.getByRole("button", { name: "Cancel" }).click();

  // Focus should return to the trigger
  await expect(trigger).toBeFocused();
});
```

## Color & Contrast

### High Contrast Mode

```typescript
test("works in high contrast mode", async ({ page }) => {
  await page.emulateMedia({ forcedColors: "active" });
  await page.goto("/");

  // Verify key elements are visible
  await expect(page.getByRole("navigation")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign In" })).toBeVisible();

  // Take screenshot for visual verification
  await expect(page).toHaveScreenshot("high-contrast.png");
});
```

### Reduced Motion

```typescript
test("respects reduced motion preference", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");

  // Animations should be disabled
  const hero = page.getByTestId("hero-animation");
  const animation = await hero.evaluate(
    (el) => getComputedStyle(el).animationDuration,
  );

  expect(animation).toBe("0s");
});
```

## CI Integration

### A11y as CI Gate

```typescript
// playwright.config.ts
export default defineConfig({
  projects: [
    {
      name: "a11y",
      testMatch: /.*\.a11y\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
```

```yaml
# .github/workflows/a11y.yml
- name: Run accessibility tests
  run: npx playwright test --project=a11y
```

## Anti-Patterns to Avoid

| Anti-Pattern                  | Problem                      | Solution                                   |
| ----------------------------- | ---------------------------- | ------------------------------------------ |
| Testing a11y only on homepage | Misses issues on other pages | Test all critical user flows               |
| Ignoring all violations       | No value from tests          | Address or explicitly exclude known issues |
| Only automated testing        | Misses many a11y issues      | Combine with manual testing                |
| Testing without screen reader | Misses interaction issues    | Test with VoiceOver/NVDA periodically      |

## Related References

- **Locators**: See [locators.md](../core/locators.md) for role-based selectors
- **Visual testing**: See [test-suite-structure.md](../core/test-suite-structure.md) for screenshot comparison
