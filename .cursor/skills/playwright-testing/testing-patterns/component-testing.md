# Component Testing

## Table of Contents

1. [Setup & Configuration](#setup--configuration)
2. [Mounting Components](#mounting-components)
3. [Props & State Testing](#props--state-testing)
4. [Events & Interactions](#events--interactions)
5. [Slots & Children](#slots--children)
6. [Mocking Dependencies](#mocking-dependencies)
7. [Framework-Specific Patterns](#framework-specific-patterns)

## Setup & Configuration

### Installation

```bash
# React
npm init playwright@latest -- --ct

# Vue
npm init playwright@latest -- --ct

# Svelte
npm init playwright@latest -- --ct

# Solid
npm init playwright@latest -- --ct
```

### Configuration

```typescript
// playwright-ct.config.ts
import { defineConfig, devices } from "@playwright/experimental-ct-react";

export default defineConfig({
  testDir: "./tests/components",
  snapshotDir: "./tests/components/__snapshots__",

  use: {
    ctPort: 3100,
    ctViteConfig: {
      resolve: {
        alias: {
          "@": "/src",
        },
      },
    },
  },

  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
});
```

### Project Structure

```
src/
  components/
    Button.tsx
    Modal.tsx
tests/
  components/
    Button.spec.tsx
    Modal.spec.tsx
playwright/
  index.html    # CT entry point
  index.tsx     # CT setup (providers, styles)
```

## Mounting Components

### Basic Mount

```tsx
// Button.spec.tsx
import { test, expect } from "@playwright/experimental-ct-react";
import { Button } from "@/components/Button";

test("renders button with text", async ({ mount }) => {
  const component = await mount(<Button>Click me</Button>);

  await expect(component).toContainText("Click me");
  await expect(component).toBeVisible();
});
```

### Mount with Props

```tsx
test("renders with all props", async ({ mount }) => {
  const component = await mount(
    <Button variant="primary" size="large" disabled={false} icon="check">
      Submit
    </Button>,
  );

  await expect(component).toHaveClass(/primary/);
  await expect(component).toHaveClass(/large/);
  await expect(component.locator("svg")).toBeVisible(); // icon
});
```

### Mount with Wrapper/Provider

```tsx
// playwright/index.tsx - Global providers
import { ThemeProvider } from "@/providers/theme";
import { QueryClientProvider } from "@tanstack/react-query";
import "@/styles/globals.css";

export default function PlaywrightWrapper({ children }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>{children}</ThemeProvider>
    </QueryClientProvider>
  );
}
```

```tsx
// Or per-test wrapper
test("with custom provider", async ({ mount }) => {
  const component = await mount(
    <AuthProvider initialUser={{ name: "Test" }}>
      <UserProfile />
    </AuthProvider>,
  );

  await expect(component.getByText("Test")).toBeVisible();
});
```

## Props & State Testing

### Testing Prop Variations

```tsx
test.describe("Button variants", () => {
  const variants = ["primary", "secondary", "danger", "ghost"] as const;

  for (const variant of variants) {
    test(`renders ${variant} variant`, async ({ mount }) => {
      const component = await mount(<Button variant={variant}>Button</Button>);
      await expect(component).toHaveClass(new RegExp(variant));
    });
  }
});
```

### Updating Props

```tsx
test("responds to prop changes", async ({ mount }) => {
  const component = await mount(<Counter initialCount={0} />);

  await expect(component.getByTestId("count")).toHaveText("0");

  // Update props
  await component.update(<Counter initialCount={10} />);
  await expect(component.getByTestId("count")).toHaveText("10");
});
```

### Testing Controlled Components

```tsx
test("controlled input", async ({ mount }) => {
  let externalValue = "";

  const component = await mount(
    <Input
      value={externalValue}
      onChange={(e) => {
        externalValue = e.target.value;
      }}
    />,
  );

  await component.locator("input").fill("hello");

  // For controlled components, update with new value
  await component.update(
    <Input value="hello" onChange={(e) => (externalValue = e.target.value)} />,
  );

  await expect(component.locator("input")).toHaveValue("hello");
});
```

### Testing Internal State

```tsx
test("internal state updates", async ({ mount }) => {
  const component = await mount(<Toggle defaultChecked={false} />);

  // Initial state
  await expect(component.locator('[role="switch"]')).toHaveAttribute(
    "aria-checked",
    "false",
  );

  // Trigger state change
  await component.click();

  // Verify state updated
  await expect(component.locator('[role="switch"]')).toHaveAttribute(
    "aria-checked",
    "true",
  );
});
```

## Events & Interactions

### Testing Click Events

```tsx
test("click event fires", async ({ mount }) => {
  let clicked = false;

  const component = await mount(
    <Button onClick={() => (clicked = true)}>Click</Button>,
  );

  await component.click();

  expect(clicked).toBe(true);
});
```

### Testing Event Payloads

```tsx
test("onChange provides correct value", async ({ mount }) => {
  const values: string[] = [];

  const component = await mount(
    <Select
      options={["a", "b", "c"]}
      onChange={(value) => values.push(value)}
    />,
  );

  await component.getByRole("combobox").click();
  await component.getByRole("option", { name: "b" }).click();

  expect(values).toEqual(["b"]);
});
```

### Testing Form Submission

```tsx
test("form submission", async ({ mount }) => {
  let submittedData: FormData | null = null;

  const component = await mount(
    <LoginForm
      onSubmit={(data) => {
        submittedData = data;
      }}
    />,
  );

  await component.getByLabel("Email").fill("test@example.com");
  await component.getByLabel("Password").fill("secret123");
  await component.getByRole("button", { name: "Sign in" }).click();

  expect(submittedData).toEqual({
    email: "test@example.com",
    password: "secret123",
  });
});
```

### Testing Keyboard Interactions

```tsx
test("keyboard navigation", async ({ mount }) => {
  const component = await mount(
    <Dropdown options={["Apple", "Banana", "Cherry"]} />,
  );

  // Open dropdown
  await component.getByRole("button").click();

  // Navigate with keyboard
  await component.press("ArrowDown");
  await component.press("ArrowDown");
  await component.press("Enter");

  await expect(component.getByRole("button")).toHaveText("Banana");
});
```

## Slots & Children

### Testing Children Content

```tsx
test("renders children", async ({ mount }) => {
  const component = await mount(
    <Card>
      <h2>Title</h2>
      <p>Description</p>
    </Card>,
  );

  await expect(component.getByRole("heading")).toHaveText("Title");
  await expect(component.getByText("Description")).toBeVisible();
});
```

### Testing Named Slots (Vue)

```tsx
// Vue component with slots
test("renders named slots", async ({ mount }) => {
  const component = await mount(Modal, {
    slots: {
      header: "<h2>Modal Title</h2>",
      default: "<p>Modal content</p>",
      footer: "<button>Close</button>",
    },
  });

  await expect(component.getByRole("heading")).toHaveText("Modal Title");
  await expect(component.getByRole("button")).toHaveText("Close");
});
```

### Testing Render Props

```tsx
test("render prop pattern", async ({ mount }) => {
  const component = await mount(
    <DataFetcher url="/api/users">
      {({ data, loading }) =>
        loading ? <span>Loading...</span> : <span>{data.name}</span>
      }
    </DataFetcher>,
  );

  // Initially loading
  await expect(component.getByText("Loading...")).toBeVisible();

  // After data loads
  await expect(component.getByText(/User/)).toBeVisible();
});
```

## Mocking Dependencies

### Mocking Imports

```tsx
// playwright/index.tsx - Mock at setup level
import { beforeMount } from "@playwright/experimental-ct-react/hooks";

beforeMount(async ({ hooksConfig }) => {
  // Mock analytics
  window.analytics = {
    track: () => {},
    identify: () => {},
  };

  // Mock feature flags
  if (hooksConfig?.featureFlags) {
    window.__FEATURE_FLAGS__ = hooksConfig.featureFlags;
  }
});
```

```tsx
// Test with mocked config
test("with feature flag", async ({ mount }) => {
  const component = await mount(<FeatureComponent />, {
    hooksConfig: {
      featureFlags: { newFeature: true },
    },
  });

  await expect(component.getByText("New Feature")).toBeVisible();
});
```

### Mocking API Calls

```tsx
test("component with API", async ({ mount, page }) => {
  // Mock API before mounting
  await page.route("**/api/user", (route) => {
    route.fulfill({
      json: { id: 1, name: "Test User" },
    });
  });

  const component = await mount(<UserProfile userId={1} />);

  await expect(component.getByText("Test User")).toBeVisible();
});
```

### Mocking Hooks

```tsx
// Mock custom hook via module mock
test("with mocked hook", async ({ mount }) => {
  const component = await mount(<Dashboard />, {
    hooksConfig: {
      mockAuth: { user: { name: "Admin" }, isAdmin: true },
    },
  });

  await expect(component.getByText("Admin Panel")).toBeVisible();
});
```

## Framework-Specific Patterns

### React Testing

```tsx
// React with refs
test("exposes ref methods", async ({ mount }) => {
  let inputRef: HTMLInputElement | null = null;

  const component = await mount(<Input ref={(el) => (inputRef = el)} />);

  await component.locator("input").fill("test");
  expect(inputRef?.value).toBe("test");
});

// React with context
test("uses context", async ({ mount }) => {
  const component = await mount(
    <UserContext.Provider value={{ name: "Test" }}>
      <UserGreeting />
    </UserContext.Provider>,
  );

  await expect(component).toContainText("Hello, Test");
});
```

### Vue Testing

```tsx
import { test, expect } from "@playwright/experimental-ct-vue";
import MyInput from "@/components/MyInput.vue";

// With v-model
test("v-model binding", async ({ mount }) => {
  let modelValue = "";
  const component = await mount(MyInput, {
    props: {
      modelValue,
      "onUpdate:modelValue": (v: string) => (modelValue = v),
    },
  });

  await component.locator("input").fill("test");
  expect(modelValue).toBe("test");
});
```

### Svelte Testing

```tsx
import { test, expect } from "@playwright/experimental-ct-svelte";
import Counter from "./Counter.svelte";

test("Svelte component", async ({ mount }) => {
  const component = await mount(Counter, { props: { initialCount: 5 } });
  await expect(component.getByTestId("count")).toHaveText("5");
  await component.getByRole("button", { name: "+" }).click();
  await expect(component.getByTestId("count")).toHaveText("6");
});
```

## Anti-Patterns to Avoid

| Anti-Pattern                   | Problem             | Solution                          |
| ------------------------------ | ------------------- | --------------------------------- |
| Testing implementation details | Brittle tests       | Test behavior, not internal state |
| Snapshot testing everything    | Maintenance burden  | Use for visual regression only    |
| Not isolating components       | Hidden dependencies | Mock all external dependencies    |
| Testing framework behavior     | Redundant           | Focus on your component logic     |
| Skipping accessibility         | Misses real issues  | Include a11y checks in CT         |

## Related References

- **Accessibility**: See [accessibility.md](accessibility.md) for a11y testing in components
- **Fixtures**: See [fixtures-hooks.md](../core/fixtures-hooks.md) for shared test setup
