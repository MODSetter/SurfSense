# Locator Strategies

## Table of Contents

1. [Priority Order](#priority-order)
2. [User-Facing Locators](#user-facing-locators)
3. [Filtering & Chaining](#filtering--chaining)
4. [Dynamic Content](#dynamic-content)
5. [Shadow DOM](#shadow-dom)
6. [Iframes](#iframes)

## Priority Order

Use locators in this order of preference:

1. **Role-based** (most resilient): `getByRole`
2. **Label-based**: `getByLabel`, `getByPlaceholder`
3. **Text-based**: `getByText`, `getByTitle`
4. **Test IDs** (when semantic locators aren't possible): `getByTestId`
5. **CSS/XPath** (last resort): `locator('css=...')`, `locator('xpath=...')`

## User-Facing Locators

### getByRole

Most robust approach - matches how users and assistive technology perceive the page.

```typescript
// Buttons
page.getByRole("button", { name: "Submit", exact: true }); // exact accessible name
page.getByRole("button", { name: /submit/i }); // flexible case-insensitive match

// Links
page.getByRole("link", { name: "Home" });

// Form elements
page.getByRole("textbox", { name: "Email" });
page.getByRole("checkbox", { name: "Remember me" });
page.getByRole("combobox", { name: "Country" });
page.getByRole("radio", { name: "Option A" });

// Headings
page.getByRole("heading", { name: "Welcome", level: 1 });

// Lists & items
page.getByRole("list").getByRole("listitem");

// Navigation & regions
page.getByRole("navigation");
page.getByRole("main");
page.getByRole("dialog");
page.getByRole("alert");
```

### getByLabel

For form elements with associated labels.

```typescript
// Input with <label for="email">
page.getByLabel("Email address");

// Input with aria-label
page.getByLabel("Search");

// Exact match
page.getByLabel("Email", { exact: true });
```

### getByPlaceholder

```typescript
page.getByPlaceholder("Enter your email");
page.getByPlaceholder(/email/i);
```

### getByText

```typescript
// Partial match (default)
page.getByText("Welcome");

// Exact match
page.getByText("Welcome to our site", { exact: true });

// Regex
page.getByText(/welcome/i);
```

### getByTestId

Configure custom test ID attribute in `playwright.config.ts`:

```typescript
use: {
  testIdAttribute: "data-testid"; // default
}
```

Usage:

```typescript
// HTML: <button data-testid="submit-btn">Submit</button>
page.getByTestId("submit-btn");
```

## Filtering & Chaining

### filter()

Narrow down locators:

```typescript
// Filter by text
page.getByRole("listitem").filter({ hasText: "Product" });

// Filter by NOT having text
page.getByRole("listitem").filter({ hasNotText: "Out of stock" });

// Filter by child locator
page.getByRole("listitem").filter({
  has: page.getByRole("button", { name: "Buy" }),
});

// Combine filters
page
  .getByRole("listitem")
  .filter({ hasText: "Product" })
  .filter({ has: page.getByText("$9.99") });
```

### Chaining

```typescript
// Navigate down the DOM tree
page.getByRole("article").getByRole("heading");

// Get parent/ancestor
page.getByText("Child").locator("..");
page.getByText("Child").locator("xpath=ancestor::article");
```

### nth() and first()/last()

```typescript
page.getByRole("listitem").first();
page.getByRole("listitem").last();
page.getByRole("listitem").nth(2); // 0-indexed
```

## Dynamic Content

### Waiting for Elements

Locators auto-wait for actionability by default. For explicit state waiting:

```typescript
await page.getByRole("button").waitFor({ state: "visible" });
await page.getByText("Loading").waitFor({ state: "hidden" });
```

> **For comprehensive waiting strategies** (element state, navigation, network, polling with `toPass()`), see [assertions-waiting.md](assertions-waiting.md#waiting-strategies).

### Lists with Dynamic Items

```typescript
// Wait for specific count
await expect(page.getByRole("listitem")).toHaveCount(5);

// Get all matching elements
const items = await page.getByRole("listitem").all();
for (const item of items) {
  await expect(item).toBeVisible();
}
```

## Shadow DOM

Playwright pierces shadow DOM by default:

```typescript
// Automatically finds elements inside shadow roots
page.getByRole("button", { name: "Shadow Button" });

// Explicit shadow DOM traversal (if needed)
page.locator("my-component").locator("internal:shadow=button");
```

## Iframes

```typescript
// By frame name or URL
const frame = page.frameLocator('iframe[name="content"]');
await frame.getByRole("button").click();

// By index
const frame = page.frameLocator("iframe").first();

// Nested iframes
const nestedFrame = page.frameLocator("#outer").frameLocator("#inner");
await nestedFrame.getByText("Content").click();
```

## Debugging Locators

```typescript
// Highlight element in headed mode
await page.getByRole("button").highlight();

// Count matches
const count = await page.getByRole("listitem").count();

// Check if exists without waiting
const exists = (await page.getByRole("button").count()) > 0;

// Use Playwright Inspector
// PWDEBUG=1 npx playwright test
```

## Common Issues & Solutions

| Issue                   | Solution                                         |
| ----------------------- | ------------------------------------------------ |
| Multiple elements match | Add filters or use `nth()`, `first()`, `last()`  |
| Element not found       | Check visibility, wait for load, verify selector |
| Stale element           | Locators are lazy; re-query if DOM changes       |
| Dynamic IDs             | Use stable attributes like role, text, test-id   |
| Hidden elements         | Use `{ force: true }` only when necessary        |

## Anti-Patterns to Avoid

| Anti-Pattern                      | Problem                           | Solution                                          |
| --------------------------------- | --------------------------------- | ------------------------------------------------- |
| `page.locator('.btn-primary')`    | Brittle, implementation-dependent | `page.getByRole('button', { name: 'Submit' })`    |
| `page.locator('#dynamic-id-123')` | Breaks when IDs change            | Use stable attributes like role, text, or test-id |
| Testing implementation details    | Breaks on refactoring             | Test user-visible behavior                        |

## Related References

- **Debugging selector issues**: See [debugging.md](../debugging/debugging.md) for troubleshooting
- **Waiting for elements**: See [assertions-waiting.md](assertions-waiting.md) for waiting strategies
- **Using in Page Objects**: See [page-object-model.md](page-object-model.md) for organizing locators
