# Multi-User & Collaboration Testing

## Table of Contents

1. [Multiple Browser Contexts](#multiple-browser-contexts)
2. [Real-Time Collaboration](#real-time-collaboration)
3. [Role-Based Testing](#role-based-testing)
4. [Concurrent Actions](#concurrent-actions)
5. [Chat & Messaging](#chat--messaging)

## Multiple Browser Contexts

### Two Users in Same Test

```typescript
test("two users see each other's changes", async ({ browser }) => {
  // Create two isolated contexts (like two browsers)
  const userAContext = await browser.newContext();
  const userBContext = await browser.newContext();

  const userAPage = await userAContext.newPage();
  const userBPage = await userBContext.newPage();

  // Both users go to the same document
  await userAPage.goto("/doc/shared-123");
  await userBPage.goto("/doc/shared-123");

  // User A types
  await userAPage.getByLabel("Content").fill("Hello from User A");

  // User B should see the change
  await expect(userBPage.getByText("Hello from User A")).toBeVisible();

  // Cleanup
  await userAContext.close();
  await userBContext.close();
});
```

### Multiple Users with Auth States

```typescript
test("admin and user interaction", async ({ browser }) => {
  // Load different auth states
  const adminContext = await browser.newContext({
    storageState: ".auth/admin.json",
  });
  const userContext = await browser.newContext({
    storageState: ".auth/user.json",
  });

  const adminPage = await adminContext.newPage();
  const userPage = await userContext.newPage();

  // User submits request
  await userPage.goto("/support");
  await userPage.getByLabel("Message").fill("Need help!");
  await userPage.getByRole("button", { name: "Submit" }).click();

  // Admin sees and responds
  await adminPage.goto("/admin/tickets");
  await expect(adminPage.getByText("Need help!")).toBeVisible();
  await adminPage.getByRole("button", { name: "Reply" }).click();
  await adminPage.getByLabel("Response").fill("How can I help?");
  await adminPage.getByRole("button", { name: "Send" }).click();

  // User sees response
  await expect(userPage.getByText("How can I help?")).toBeVisible();

  await adminContext.close();
  await userContext.close();
});
```

### Multi-User Fixture

```typescript
// fixtures/multi-user.fixture.ts
import { test as base, Browser, BrowserContext, Page } from "@playwright/test";

type UserSession = {
  context: BrowserContext;
  page: Page;
};

type MultiUserFixtures = {
  createUser: (authState?: string) => Promise<UserSession>;
};

export const test = base.extend<MultiUserFixtures>({
  createUser: async ({ browser }, use) => {
    const sessions: UserSession[] = [];

    await use(async (authState) => {
      const context = await browser.newContext({
        storageState: authState,
      });
      const page = await context.newPage();
      sessions.push({ context, page });
      return { context, page };
    });

    // Cleanup all sessions
    for (const session of sessions) {
      await session.context.close();
    }
  },
});

// Usage
test("3 users collaborate", async ({ createUser }) => {
  const alice = await createUser(".auth/alice.json");
  const bob = await createUser(".auth/bob.json");
  const charlie = await createUser(".auth/charlie.json");

  // All navigate to same room
  await alice.page.goto("/room/123");
  await bob.page.goto("/room/123");
  await charlie.page.goto("/room/123");

  // Test interactions...
});
```

## Real-Time Collaboration

### Collaborative Document

```typescript
test("real-time collaborative editing", async ({ browser }) => {
  const user1 = await browser.newContext();
  const user2 = await browser.newContext();

  const page1 = await user1.newPage();
  const page2 = await user2.newPage();

  await page1.goto("/docs/shared");
  await page2.goto("/docs/shared");

  // User 1 types at the beginning
  const editor1 = page1.getByRole("textbox");
  await editor1.click();
  await editor1.press("Home");
  await editor1.type("User 1: ");

  // User 2 types at the end
  const editor2 = page2.getByRole("textbox");
  await editor2.click();
  await editor2.press("End");
  await editor2.type(" - User 2");

  // Both should see combined result
  await expect(page1.getByRole("textbox")).toContainText("User 1:");
  await expect(page1.getByRole("textbox")).toContainText("- User 2");
  await expect(page2.getByRole("textbox")).toContainText("User 1:");
  await expect(page2.getByRole("textbox")).toContainText("- User 2");

  await user1.close();
  await user2.close();
});
```

### Cursor Presence

```typescript
test("shows other user cursors", async ({ browser }) => {
  const ctx1 = await browser.newContext();
  const ctx2 = await browser.newContext();

  const page1 = await ctx1.newPage();
  const page2 = await ctx2.newPage();

  // Mock to identify users
  await page1.route("**/api/me", (route) =>
    route.fulfill({ json: { id: "user-1", name: "Alice" } }),
  );
  await page2.route("**/api/me", (route) =>
    route.fulfill({ json: { id: "user-2", name: "Bob" } }),
  );

  await page1.goto("/whiteboard/123");
  await page2.goto("/whiteboard/123");

  // Move cursor on page1
  await page1.mouse.move(200, 200);

  // Page2 should see Alice's cursor
  await expect(page2.getByTestId("cursor-user-1")).toBeVisible();
  await expect(page2.getByText("Alice")).toBeVisible();

  await ctx1.close();
  await ctx2.close();
});
```

## Role-Based Testing

### Test RBAC

```typescript
const roles = [
  { role: "admin", canDelete: true, canEdit: true, canView: true },
  { role: "editor", canDelete: false, canEdit: true, canView: true },
  { role: "viewer", canDelete: false, canEdit: false, canView: true },
];

for (const { role, canDelete, canEdit, canView } of roles) {
  test(`${role} permissions`, async ({ browser }) => {
    const context = await browser.newContext({
      storageState: `.auth/${role}.json`,
    });
    const page = await context.newPage();

    await page.goto("/document/123");

    // Check view permission
    if (canView) {
      await expect(page.getByTestId("content")).toBeVisible();
    } else {
      await expect(page.getByText("Access denied")).toBeVisible();
    }

    // Check edit permission
    const editButton = page.getByRole("button", { name: "Edit" });
    if (canEdit) {
      await expect(editButton).toBeEnabled();
    } else {
      await expect(editButton).toBeDisabled();
    }

    // Check delete permission
    const deleteButton = page.getByRole("button", { name: "Delete" });
    if (canDelete) {
      await expect(deleteButton).toBeVisible();
    } else {
      await expect(deleteButton).toBeHidden();
    }

    await context.close();
  });
}
```

### Permission Escalation Test

```typescript
test("cannot access admin routes as user", async ({ browser }) => {
  const userContext = await browser.newContext({
    storageState: ".auth/user.json",
  });
  const page = await userContext.newPage();

  // Try to access admin page directly
  await page.goto("/admin/users");

  // Should redirect or show error
  await expect(page).not.toHaveURL("/admin/users");
  await expect(page.getByText("Access denied")).toBeVisible();

  await userContext.close();
});
```

## Concurrent Actions

### Race Condition Testing

```typescript
test("handles concurrent edits", async ({ browser }) => {
  const ctx1 = await browser.newContext();
  const ctx2 = await browser.newContext();

  const page1 = await ctx1.newPage();
  const page2 = await ctx2.newPage();

  await page1.goto("/item/123");
  await page2.goto("/item/123");

  // Both click edit at the same time
  await Promise.all([
    page1.getByRole("button", { name: "Edit" }).click(),
    page2.getByRole("button", { name: "Edit" }).click(),
  ]);

  // Both try to save different values
  await page1.getByLabel("Name").fill("Value from User 1");
  await page2.getByLabel("Name").fill("Value from User 2");

  await Promise.all([
    page1.getByRole("button", { name: "Save" }).click(),
    page2.getByRole("button", { name: "Save" }).click(),
  ]);

  // One should succeed, one should get conflict error
  const page1HasConflict = await page1.getByText("Conflict").isVisible();
  const page2HasConflict = await page2.getByText("Conflict").isVisible();

  // Exactly one should have conflict
  expect(page1HasConflict || page2HasConflict).toBe(true);
  expect(page1HasConflict && page2HasConflict).toBe(false);

  await ctx1.close();
  await ctx2.close();
});
```

### Optimistic Locking Test

```typescript
test("optimistic locking prevents overwrites", async ({ browser }) => {
  const ctx1 = await browser.newContext();
  const ctx2 = await browser.newContext();

  const page1 = await ctx1.newPage();
  const page2 = await ctx2.newPage();

  // Both load the same version
  await page1.goto("/record/123");
  await page2.goto("/record/123");

  // User 1 edits and saves first
  await page1.getByRole("button", { name: "Edit" }).click();
  await page1.getByLabel("Value").fill("Updated by User 1");
  await page1.getByRole("button", { name: "Save" }).click();
  await expect(page1.getByText("Saved")).toBeVisible();

  // User 2 tries to save with stale version
  await page2.getByRole("button", { name: "Edit" }).click();
  await page2.getByLabel("Value").fill("Updated by User 2");
  await page2.getByRole("button", { name: "Save" }).click();

  // Should fail with version conflict
  await expect(page2.getByText("Someone else modified this")).toBeVisible();
  await expect(page2.getByRole("button", { name: "Reload" })).toBeVisible();

  await ctx1.close();
  await ctx2.close();
});
```

## Chat & Messaging

### Real-Time Chat

```typescript
test("chat messages sync between users", async ({ browser }) => {
  const aliceCtx = await browser.newContext();
  const bobCtx = await browser.newContext();

  const alicePage = await aliceCtx.newPage();
  const bobPage = await bobCtx.newPage();

  // Setup user identities
  await alicePage.route("**/api/me", (r) =>
    r.fulfill({ json: { name: "Alice" } }),
  );
  await bobPage.route("**/api/me", (r) => r.fulfill({ json: { name: "Bob" } }));

  await alicePage.goto("/chat/room-1");
  await bobPage.goto("/chat/room-1");

  // Alice sends message
  await alicePage.getByLabel("Message").fill("Hi Bob!");
  await alicePage.getByRole("button", { name: "Send" }).click();

  // Bob sees it
  await expect(bobPage.getByText("Alice: Hi Bob!")).toBeVisible();

  // Bob replies
  await bobPage.getByLabel("Message").fill("Hey Alice!");
  await bobPage.getByRole("button", { name: "Send" }).click();

  // Alice sees it
  await expect(alicePage.getByText("Bob: Hey Alice!")).toBeVisible();

  await aliceCtx.close();
  await bobCtx.close();
});
```

## Anti-Patterns to Avoid

| Anti-Pattern                  | Problem                       | Solution                     |
| ----------------------------- | ----------------------------- | ---------------------------- |
| Sharing context between users | State leaks, not isolated     | Create separate contexts     |
| Not closing contexts          | Memory leak, browser overload | Always close in cleanup      |
| Hardcoded timing for sync     | Flaky tests                   | Use `expect().toBeVisible()` |
| Testing only single user      | Misses collaboration bugs     | Test multi-user scenarios    |

## Related References

- **Authentication**: See [fixtures-hooks.md](../core/fixtures-hooks.md) for auth setup
- **WebSockets**: See [websockets.md](../browser-apis/websockets.md) for real-time mocking
