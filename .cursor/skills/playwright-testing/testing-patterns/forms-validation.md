# Form Testing Patterns

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Patterns](#patterns)
3. [Decision Guide](#decision-guide)
4. [Anti-Patterns](#anti-patterns)
5. [Troubleshooting](#troubleshooting)

> **When to use**: Testing form filling, submission, validation messages, multi-step wizards, dynamic fields, and auto-complete interactions.

## Quick Reference

```typescript
// Text input
await page.getByLabel("Username").fill("john_doe");

// Select dropdown
await page.getByLabel("Region").selectOption("EU");
await page.getByLabel("Region").selectOption({ label: "Europe" });

// Checkbox and radio
await page.getByLabel("Subscribe").check();
await page.getByLabel("Priority shipping").click();

// Date input
await page.getByLabel("Departure").fill("2025-08-20");

// Clear a field
await page.getByLabel("Username").clear();

// Submit
await page.getByRole("button", { name: "Register" }).click();

// Verify validation error
await expect(page.getByText("Username is required")).toBeVisible();
```

## Patterns

### Auto-Complete and Typeahead Fields

**Use when**: Testing search fields, address lookups, mention pickers, or any input that shows suggestions as the user types.

```typescript
test("select from typeahead suggestions", async ({ page }) => {
  await page.goto("/products");

  const searchBox = page.getByRole("combobox", { name: "Find product" });
  await searchBox.pressSequentially("lapt", { delay: 100 });

  const suggestionList = page.getByRole("listbox");
  await expect(suggestionList).toBeVisible();

  await suggestionList.getByRole("option", { name: "Laptop Pro" }).click();
  await expect(searchBox).toHaveValue("Laptop Pro");
});

test("typeahead with API-driven suggestions", async ({ page }) => {
  await page.goto("/shipping");

  const streetField = page.getByLabel("Street");
  const responsePromise = page.waitForResponse("**/api/address-lookup*");
  await streetField.pressSequentially("456 Elm", { delay: 50 });

  await responsePromise;

  await page.getByRole("option", { name: /456 Elm St/ }).click();

  await expect(page.getByLabel("Town")).toHaveValue("Austin");
  await expect(page.getByLabel("State")).toHaveValue("TX");
  await expect(page.getByLabel("Postal code")).toHaveValue("78701");
});

test("dismiss suggestions and enter custom value", async ({ page }) => {
  await page.goto("/labels");

  const labelInput = page.getByLabel("New label");
  await labelInput.pressSequentially("my-label");

  await labelInput.press("Escape");
  await expect(page.getByRole("listbox")).not.toBeVisible();

  await labelInput.press("Enter");
  await expect(page.getByText("my-label")).toBeVisible();
});
```

### Dynamic Forms — Conditional Fields

**Use when**: Form fields appear, disappear, or change based on the value of other fields.

```typescript
test("conditional fields appear based on selection", async ({ page }) => {
  await page.goto("/loan/apply");

  await page.getByLabel("Applicant type").selectOption("corporate");

  await expect(page.getByLabel("Business name")).toBeVisible();
  await expect(page.getByLabel("EIN")).toBeVisible();

  await page.getByLabel("Business name").fill("TechCorp Inc");
  await page.getByLabel("EIN").fill("98-7654321");

  await page.getByLabel("Applicant type").selectOption("individual");
  await expect(page.getByLabel("Business name")).not.toBeVisible();
  await expect(page.getByLabel("EIN")).not.toBeVisible();
});

test("checkbox toggles additional section", async ({ page }) => {
  await page.goto("/delivery");

  await page.getByLabel("Separate invoice address").check();

  const invoiceSection = page.getByRole("group", { name: "Invoice address" });
  await expect(invoiceSection).toBeVisible();

  await invoiceSection.getByLabel("Address").fill("789 Pine Rd");
  await invoiceSection.getByLabel("City").fill("Denver");

  await page.getByLabel("Separate invoice address").uncheck();
  await expect(invoiceSection).not.toBeVisible();
});

test("dependent dropdown chains", async ({ page }) => {
  await page.goto("/region-selector");

  await page.getByLabel("Country").selectOption("CA");

  const provinceDropdown = page.getByLabel("Province");
  await expect(provinceDropdown.getByRole("option")).not.toHaveCount(0);

  await provinceDropdown.selectOption("ON");

  const cityDropdown = page.getByLabel("City");
  await expect(cityDropdown.getByRole("option")).not.toHaveCount(0);

  await cityDropdown.selectOption({ label: "Toronto" });
});
```

### Multi-Step Forms and Wizards

**Use when**: The form spans multiple pages or steps, with next/previous navigation and per-step validation.

```typescript
test("complete a multi-step booking wizard", async ({ page }) => {
  await page.goto("/booking");

  await test.step("enter guest information", async () => {
    await expect(
      page.getByRole("heading", { name: "Guest Info" }),
    ).toBeVisible();

    await page.getByLabel("Full name").fill("Alice Smith");
    await page.getByLabel("Email").fill("alice@test.com");
    await page.getByLabel("Phone").fill("555-1234");

    await page.getByRole("button", { name: "Next" }).click();
  });

  await test.step("select room options", async () => {
    await expect(
      page.getByRole("heading", { name: "Room Selection" }),
    ).toBeVisible();

    await page.getByLabel("Room type").selectOption("suite");
    await page.getByLabel("Check-in").fill("2025-09-01");
    await page.getByLabel("Check-out").fill("2025-09-05");

    await page.getByRole("button", { name: "Next" }).click();
  });

  await test.step("confirm booking", async () => {
    await expect(
      page.getByRole("heading", { name: "Confirmation" }),
    ).toBeVisible();

    await expect(page.getByText("Alice Smith")).toBeVisible();
    await expect(page.getByText("suite")).toBeVisible();

    await page.getByRole("button", { name: "Confirm booking" }).click();
  });

  await expect(
    page.getByRole("heading", { name: "Booking complete" }),
  ).toBeVisible();
});

test("wizard validates each step before proceeding", async ({ page }) => {
  await page.goto("/booking");

  await page.getByRole("button", { name: "Next" }).click();

  await expect(page.getByRole("heading", { name: "Guest Info" })).toBeVisible();
  await expect(page.getByText("Full name is required")).toBeVisible();
});

test("wizard supports going back without losing data", async ({ page }) => {
  await page.goto("/booking");

  await page.getByLabel("Full name").fill("Alice Smith");
  await page.getByLabel("Email").fill("alice@test.com");
  await page.getByLabel("Phone").fill("555-1234");
  await page.getByRole("button", { name: "Next" }).click();

  await page.getByRole("button", { name: "Previous" }).click();

  await expect(page.getByLabel("Full name")).toHaveValue("Alice Smith");
  await expect(page.getByLabel("Email")).toHaveValue("alice@test.com");
});
```

### Form Submission and Response Handling

**Use when**: Testing what happens after a form is submitted — success messages, redirects, error responses from the server, and loading states during submission.

```typescript
test("successful form submission shows confirmation", async ({ page }) => {
  await page.goto("/feedback");

  await page.getByLabel("Subject").fill("Feature request");
  await page.getByLabel("Email").fill("user@test.com");
  await page.getByLabel("Details").fill("Please add dark mode");

  const responsePromise = page.waitForResponse("**/api/feedback");
  await page.getByRole("button", { name: "Submit feedback" }).click();
  const response = await responsePromise;

  expect(response.status()).toBe(200);
  await expect(page.getByText("Feedback received")).toBeVisible();
});

test("form submission shows server-side validation errors", async ({
  page,
}) => {
  await page.goto("/signup");

  await page.getByLabel("Email").fill("existing@test.com");
  await page.getByLabel("Password", { exact: true }).fill("Secure1@pass");
  await page.getByRole("button", { name: "Sign up" }).click();

  await expect(
    page.getByText("Email address already registered"),
  ).toBeVisible();
});

test("form shows loading state during submission", async ({ page }) => {
  await page.goto("/feedback");

  await page.getByLabel("Subject").fill("Bug report");
  await page.getByLabel("Email").fill("user@test.com");
  await page.getByLabel("Details").fill("Found an issue");

  const submit = page.getByRole("button", {
    name: /Submit feedback|Submitting/,
  });
  await submit.click();

  await expect(submit).toHaveText(/Submitting/);
  await expect(submit).toBeDisabled();

  await expect(submit).toHaveText("Submit feedback");
  await expect(submit).toBeEnabled();
});

test("form redirects after successful submission", async ({ page }) => {
  await page.goto("/auth/login");

  await page.getByLabel("Email").fill("admin@test.com");
  await page.getByLabel("Password").fill("admin123");
  await page.getByRole("button", { name: "Log in" }).click();

  await page.waitForURL("/home");
  await expect(page.getByRole("heading", { name: "Welcome" })).toBeVisible();
});
```

### Filling Basic Form Fields

**Use when**: Testing any form with standard HTML inputs — text, email, password, number, textarea, select, checkbox, radio.

```typescript
test("fill and submit a signup form", async ({ page }) => {
  await page.goto("/signup");

  await page.getByLabel("First name").fill("Bob");
  await page.getByLabel("Last name").fill("Wilson");
  await page.getByLabel("Email").fill("bob@test.com");
  await page.getByLabel("Password", { exact: true }).fill("P@ssw0rd!");
  await page.getByLabel("Confirm password").fill("P@ssw0rd!");

  await page.getByLabel("About you").fill("Developer with 5 years experience.");
  await page.getByLabel("Years of experience").fill("5");

  await page.getByLabel("Country").selectOption("UK");
  await page.getByLabel("City").selectOption({ label: "London" });
  await page
    .getByLabel("Skills")
    .selectOption(["typescript", "playwright", "nodejs"]);

  await page.getByLabel("Accept terms").check();
  await expect(page.getByLabel("Accept terms")).toBeChecked();

  await page.getByLabel("Annual billing").check();
  await expect(page.getByLabel("Annual billing")).toBeChecked();

  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Welcome" })).toBeVisible();
});
```

### Date and Time Inputs

**Use when**: Testing native `<input type="date">`, `<input type="time">`, `<input type="datetime-local">`, or third-party date pickers.

```typescript
test("fill native date and time inputs", async ({ page }) => {
  await page.goto("/reservation");

  await page.getByLabel("Reservation date").fill("2025-07-10");
  await expect(page.getByLabel("Reservation date")).toHaveValue("2025-07-10");

  await page.getByLabel("Time slot").fill("18:00");
  await page.getByLabel("Reminder").fill("2025-07-10T17:30");
});

test("interact with a third-party date picker", async ({ page }) => {
  await page.goto("/reservation");

  await page.getByLabel("Event date").click();
  await page.getByRole("button", { name: "Next month" }).click();
  await page.getByRole("gridcell", { name: "25" }).click();

  await expect(page.getByLabel("Event date")).toHaveValue(/2025/);
});
```

### Required Field Validation

**Use when**: Testing that the form shows appropriate error messages when required fields are empty.

```typescript
test("shows validation errors for empty required fields", async ({ page }) => {
  await page.goto("/inquiry");

  await page.getByRole("button", { name: "Send inquiry" }).click();

  await expect(page.getByText("Name is required")).toBeVisible();
  await expect(page.getByText("Email is required")).toBeVisible();
  await expect(page.getByText("Question is required")).toBeVisible();

  await expect(page).toHaveURL(/\/inquiry/);
});

test("clears validation errors when fields are filled", async ({ page }) => {
  await page.goto("/inquiry");

  await page.getByRole("button", { name: "Send inquiry" }).click();
  await expect(page.getByText("Name is required")).toBeVisible();

  await page.getByLabel("Name").fill("Carol Brown");
  await page.getByLabel("Email").focus();

  await expect(page.getByText("Name is required")).not.toBeVisible();
});

test("native HTML5 validation with required attribute", async ({ page }) => {
  await page.goto("/basic-form");

  await page.getByRole("button", { name: "Submit" }).click();

  const emailInput = page.getByLabel("Email");
  const validationMessage = await emailInput.evaluate(
    (el: HTMLInputElement) => el.validationMessage,
  );
  expect(validationMessage).toBeTruthy();
});
```

### Format Validation and Custom Rules

**Use when**: Testing email format, phone number format, password strength, and business-specific validation rules.

```typescript
test("validates email format", async ({ page }) => {
  await page.goto("/signup");

  const emailField = page.getByLabel("Email");

  const invalidEmails = [
    "invalid",
    "missing@",
    "@nodomain.com",
    "has spaces@mail.com",
  ];

  for (const email of invalidEmails) {
    await emailField.fill(email);
    await emailField.blur();
    await expect(page.getByText("Enter a valid email address")).toBeVisible();
  }

  await emailField.fill("correct@domain.com");
  await emailField.blur();
  await expect(page.getByText("Enter a valid email address")).not.toBeVisible();
});

test("validates password strength rules", async ({ page }) => {
  await page.goto("/signup");

  const passwordField = page.getByLabel("Password", { exact: true });

  await passwordField.fill("Xy1!");
  await passwordField.blur();
  await expect(page.getByText("Minimum 8 characters")).toBeVisible();

  await passwordField.fill("lowercase1!");
  await passwordField.blur();
  await expect(page.getByText("Include an uppercase letter")).toBeVisible();

  await passwordField.fill("SecureP@ss1");
  await passwordField.blur();
  await expect(page.getByText(/Minimum|Include/)).not.toBeVisible();
});

test("validates custom business rule — minimum amount", async ({ page }) => {
  await page.goto("/transfer");

  await page.getByLabel("Amount").fill("5");
  await page.getByLabel("Amount").blur();
  await expect(page.getByText("Minimum transfer is $10")).toBeVisible();

  await page.getByLabel("Amount").fill("1000000");
  await page.getByLabel("Amount").blur();
  await expect(page.getByText("Maximum transfer is $100,000")).toBeVisible();

  await page.getByLabel("Amount").fill("500");
  await page.getByLabel("Amount").blur();
  await expect(page.getByText(/Minimum|Maximum/)).not.toBeVisible();
});
```

### Form Reset Testing

**Use when**: Testing "clear form" or "reset" functionality, verifying that fields return to their default values.

```typescript
test("reset button clears all fields to defaults", async ({ page }) => {
  await page.goto("/preferences");

  await page.getByLabel("Nickname").fill("CustomNick");
  await page.getByLabel("Language").selectOption("es");
  await page.getByLabel("Email alerts").uncheck();

  await page.getByRole("button", { name: "Reset" }).click();

  await expect(page.getByLabel("Nickname")).toHaveValue("");
  await expect(page.getByLabel("Language")).toHaveValue("en");
  await expect(page.getByLabel("Email alerts")).toBeChecked();
});

test("confirmation dialog before resetting a dirty form", async ({ page }) => {
  await page.goto("/document");

  await page.getByLabel("Document title").fill("Draft document");

  page.on("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Clear changes" }).click();

  await expect(page.getByLabel("Document title")).toHaveValue("");
});
```

## Decision Guide

| Scenario                             | Approach                                               | Key API                                                      |
| ------------------------------------ | ------------------------------------------------------ | ------------------------------------------------------------ |
| Standard text input                  | `fill()` (clears, then types)                          | `page.getByLabel('Field').fill('value')`                     |
| Need keystroke events (autocomplete) | `pressSequentially()` with delay                       | `locator.pressSequentially('text', { delay: 100 })`          |
| Native `<select>` dropdown           | `selectOption()` by value or label                     | `locator.selectOption('US')` or `{ label: 'United States' }` |
| Custom dropdown (ARIA listbox)       | Click trigger, then select option role                 | `getByRole('option', { name: '...' }).click()`               |
| Checkbox                             | `check()` / `uncheck()` (idempotent)                   | `locator.check()` — safe to call even if already checked     |
| Radio button                         | `check()` on the target radio                          | `page.getByLabel('Option').check()`                          |
| Date input (native)                  | `fill()` with ISO format                               | `locator.fill('2025-03-15')`                                 |
| Date picker (third-party)            | Click to open, navigate, select day                    | `getByRole('gridcell', { name: '15' }).click()`              |
| Validation errors                    | Submit, then assert error text                         | `expect(page.getByText('Required')).toBeVisible()`           |
| Multi-step wizard                    | `test.step()` per step, assert heading                 | `await test.step('Step 1', async () => { ... })`             |
| Conditional/dynamic fields           | Change trigger field, assert new field visibility      | `expect(locator).toBeVisible()` / `.not.toBeVisible()`       |
| Form submission                      | `waitForResponse` + click submit                       | Register response listener before click                      |
| Auto-complete                        | `pressSequentially()`, wait for listbox, select option | `getByRole('option', { name }).click()`                      |
| Form reset                           | Click reset, assert default values                     | `expect(locator).toHaveValue('')`                            |

## Anti-Patterns

| Don't Do This                                           | Problem                                                    | Do This Instead                                        |
| ------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------ |
| `await page.getByLabel('Field').type('value')`          | `type()` appends to existing content; does not clear first | `await page.getByLabel('Field').fill('value')`         |
| `await page.getByLabel('Option').click()`               | `click()` toggles — if already checked, it unchecks        | `await page.getByLabel('Option').check()`              |
| `await page.fill('#email', 'test@test.com')`            | CSS selector is fragile                                    | `await page.getByLabel('Email').fill('test@test.com')` |
| `await page.selectOption('select', 'US')` without label | Targets first `<select>` on page; ambiguous                | `await page.getByLabel('Country').selectOption('US')`  |
| Testing every invalid input in one test                 | Test becomes huge, slow, and hard to debug                 | One test per validation rule or group related rules    |
| `expect(await input.inputValue()).toBe('value')`        | Resolves once — no retry. Race condition.                  | `await expect(input).toHaveValue('value')`             |
| Filling fields with `page.evaluate()`                   | Bypasses event handlers (no `input`, `change` events fire) | Use `fill()` or `pressSequentially()`                  |
| Not waiting for conditional fields before filling       | `fill()` fails on hidden/detached elements                 | `await expect(field).toBeVisible()` first              |
| Hardcoding wait after selecting a dropdown              | `waitForTimeout(500)` is flaky and slow                    | Wait for the dependent element to appear               |
| Skipping server-side validation tests                   | Client-side validation can be bypassed                     | Test both client-side UX and server response           |

## Troubleshooting

### `fill()` does nothing or clears but doesn't type

**Cause**: The input field uses a contenteditable div (rich text editors), not a real `<input>` or `<textarea>`.

```typescript
const isContentEditable = await page
  .getByTestId("editor")
  .evaluate((el) => el.getAttribute("contenteditable"));

if (isContentEditable) {
  await page.getByTestId("editor").click();
  await page.getByTestId("editor").pressSequentially("Hello world");
}
```

### Date picker does not accept `fill()` value

**Cause**: Third-party date pickers often render custom UI over a hidden input. `fill()` sets the hidden input but the UI does not update.

```typescript
await page.getByLabel("Date").click();
await page.getByRole("button", { name: "Next month" }).click();
await page.getByRole("gridcell", { name: "15" }).click();

// Alternatively, if the library reads from the input on change:
await page.getByLabel("Date").fill("2025-06-15");
await page.getByLabel("Date").dispatchEvent("change");
```

### `selectOption()` throws "not a select element"

**Cause**: The dropdown is a custom component (ARIA listbox), not a native `<select>`.

```typescript
await page.getByRole("combobox", { name: "Country" }).click();
await page.getByRole("option", { name: "United States" }).click();
```

### Validation errors do not appear after `fill()` and submit

**Cause**: The validation triggers on `blur` (focus leaving the field), but `fill()` does not trigger blur automatically.

```typescript
await page.getByLabel("Email").fill("invalid");
await page.getByLabel("Email").blur();
await expect(page.getByText("Enter a valid email")).toBeVisible();

// Or move focus to the next field
await page.getByLabel("Password").focus();
```
