# Page Object Model (POM)

## Table of Contents

1. [Overview](#overview)
2. [Basic Structure](#basic-structure)
3. [Component Objects](#component-objects)
4. [Composition Patterns](#composition-patterns)
5. [Factory Functions](#factory-functions)
6. [Best Practices](#best-practices)

## Overview

Page Object Model encapsulates page structure and interactions, providing:

- **Maintainability**: Change selectors in one place
- **Reusability**: Share page interactions across tests
- **Readability**: Tests express intent, not implementation

## Basic Structure

### Page Class

```typescript
// pages/login.page.ts
import { Page, Locator, expect } from "@playwright/test";

export class LoginPage {
  readonly page: Page;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.emailInput = page.getByLabel("Email");
    this.passwordInput = page.getByLabel("Password");
    this.submitButton = page.getByRole("button", { name: "Sign in" });
    this.errorMessage = page.getByRole("alert");
  }

  async goto() {
    await this.page.goto("/login");
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  async expectError(message: string) {
    await expect(this.errorMessage).toContainText(message);
  }
}
```

### Usage in Tests

```typescript
// tests/login.spec.ts
import { test, expect } from "@playwright/test";
import { LoginPage } from "../pages/login.page";

test.describe("Login", () => {
  test("successful login redirects to dashboard", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login("user@example.com", "password123");
    await expect(page).toHaveURL("/dashboard");
  });

  test("shows error for invalid credentials", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login("invalid@example.com", "wrong");
    await loginPage.expectError("Invalid credentials");
  });
});
```

## Component Objects

For reusable UI components:

```typescript
// components/navbar.component.ts
import { Page, Locator } from "@playwright/test";

export class NavbarComponent {
  readonly container: Locator;
  readonly logo: Locator;
  readonly searchInput: Locator;
  readonly userMenu: Locator;

  constructor(page: Page) {
    this.container = page.getByRole("navigation");
    this.logo = this.container.getByRole("link", { name: "Home" });
    this.searchInput = this.container.getByRole("searchbox");
    this.userMenu = this.container.getByRole("button", { name: /user menu/i });
  }

  async search(query: string) {
    await this.searchInput.fill(query);
    await this.searchInput.press("Enter");
  }

  async openUserMenu() {
    await this.userMenu.click();
  }
}
```

```typescript
// components/modal.component.ts
import { Locator, expect } from "@playwright/test";

export class ModalComponent {
  readonly container: Locator;
  readonly title: Locator;
  readonly closeButton: Locator;
  readonly confirmButton: Locator;

  constructor(container: Locator) {
    this.container = container;
    this.title = container.getByRole("heading");
    this.closeButton = container.getByRole("button", { name: "Close" });
    this.confirmButton = container.getByRole("button", { name: "Confirm" });
  }

  async expectTitle(title: string) {
    await expect(this.title).toHaveText(title);
  }

  async close() {
    await this.closeButton.click();
  }

  async confirm() {
    await this.confirmButton.click();
  }
}
```

## Composition Patterns

### Page with Components

```typescript
// pages/dashboard.page.ts
import { Page, Locator } from "@playwright/test";
import { NavbarComponent } from "../components/navbar.component";
import { ModalComponent } from "../components/modal.component";

export class DashboardPage {
  readonly page: Page;
  readonly navbar: NavbarComponent;
  readonly newProjectButton: Locator;

  constructor(page: Page) {
    this.page = page;
    this.navbar = new NavbarComponent(page);
    this.newProjectButton = page.getByRole("button", { name: "New Project" });
  }

  async goto() {
    await this.page.goto("/dashboard");
  }

  async createProject() {
    await this.newProjectButton.click();
    return new ModalComponent(this.page.getByRole("dialog"));
  }
}
```

### Page Navigation

```typescript
// pages/base.page.ts
import { Page } from "@playwright/test";

export abstract class BasePage {
  constructor(readonly page: Page) {}

  abstract goto(): Promise<void>;

  async getTitle(): Promise<string> {
    return this.page.title();
  }
}
```

```typescript
// Return new page object on navigation
export class LoginPage extends BasePage {
  async login(email: string, password: string): Promise<DashboardPage> {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
    return new DashboardPage(this.page);
  }
}

// Usage
const loginPage = new LoginPage(page);
await loginPage.goto();
const dashboardPage = await loginPage.login("user@example.com", "pass");
await dashboardPage.expectWelcomeMessage();
```

## Factory Functions

Alternative to classes for simpler pages:

```typescript
// pages/login.page.ts
import { Page } from "@playwright/test";

export function createLoginPage(page: Page) {
  const emailInput = page.getByLabel("Email");
  const passwordInput = page.getByLabel("Password");
  const submitButton = page.getByRole("button", { name: "Sign in" });

  return {
    goto: () => page.goto("/login"),
    login: async (email: string, password: string) => {
      await emailInput.fill(email);
      await passwordInput.fill(password);
      await submitButton.click();
    },
    emailInput,
    passwordInput,
    submitButton,
  };
}

// Usage
const loginPage = createLoginPage(page);
await loginPage.goto();
await loginPage.login("user@example.com", "password");
```

## Best Practices

### Do

- **Keep locators in page objects** - Single source of truth
- **Return new page objects** when navigation occurs
- **Expose elements** for custom assertions in tests
- **Use descriptive method names** - `submitOrder()` not `clickButton()`
- **Keep methods focused** - One action per method

### Don't

- **Don't include assertions in page methods** (usually) - Keep in tests
- **Don't expose implementation details** - Hide complex interactions
- **Don't make page objects too large** - Split into components
- **Don't share state** between page object instances

### Directory Structure

```
tests/
├── pages/
│   ├── base.page.ts
│   ├── login.page.ts
│   ├── dashboard.page.ts
│   └── settings.page.ts
├── components/
│   ├── navbar.component.ts
│   ├── modal.component.ts
│   └── table.component.ts
├── fixtures/
│   └── pages.fixture.ts
└── specs/
    ├── login.spec.ts
    └── dashboard.spec.ts
```

### Using with Fixtures

```typescript
// fixtures/pages.fixture.ts
import { test as base } from "@playwright/test";
import { LoginPage } from "../pages/login.page";
import { DashboardPage } from "../pages/dashboard.page";

type Pages = {
  loginPage: LoginPage;
  dashboardPage: DashboardPage;
};

export const test = base.extend<Pages>({
  loginPage: async ({ page }, use) => {
    await use(new LoginPage(page));
  },
  dashboardPage: async ({ page }, use) => {
    await use(new DashboardPage(page));
  },
});

// Usage in tests
test("can login", async ({ loginPage }) => {
  await loginPage.goto();
  await loginPage.login("user@example.com", "password");
});
```

## Related References

- **Locator strategies**: See [locators.md](locators.md) for selecting elements
- **Fixtures**: See [fixtures-hooks.md](fixtures-hooks.md) for advanced fixture patterns
- **Test organization**: See [test-suite-structure.md](test-suite-structure.md) for structuring test suites
