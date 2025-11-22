---
name: E2E Test Coverage
about: Expand frontend end-to-end test coverage for core user flows
title: 'Add Frontend E2E Tests for Core Flows'
labels: 'testing, quality, e2e'
assignees: ''
---

## Summary
Implement Playwright or Cypress end-to-end test suites covering critical user flows to ensure real-world functionality and catch integration issues before production.

## Motivation
While backend API and hooks are well-tested, E2E tests validate complete user journeys including:
- **Real User Behavior**: Test actual user interactions, not just API contracts
- **Integration Coverage**: Verify frontend ↔ backend ↔ database integration
- **Regression Prevention**: Catch UI/UX regressions before users do
- **Confidence**: Deploy with confidence knowing core flows are verified

Current test coverage focuses on backend logic but lacks end-to-end validation of user-facing features like space sharing, media upload, and permissions enforcement.

## Proposed Implementation

### Test Framework Selection
**Recommendation: Playwright**
- Modern, fast, and reliable
- Built-in screenshot/video capture on failure
- Excellent TypeScript support
- Multi-browser testing (Chromium, Firefox, WebKit)
- Better debugging experience than Cypress

**Alternative: Cypress**
- More mature ecosystem
- Excellent developer experience
- Real-time test runner
- Component testing support

### Priority Test Flows

#### 1. **Public/Private Space Sharing & Permissions** (Critical)
```typescript
// tests/e2e/space-sharing.spec.ts
test.describe('Space Sharing Permissions', () => {
  test('admin can share space publicly', async ({ page }) => {
    await loginAsAdmin(page);
    await createSearchSpace(page, 'Public Test Space');
    await shareSpace(page, 'Public Test Space');

    // Verify space appears in public listing
    await page.goto('/dashboard/searchspaces');
    await expect(page.locator('[data-testid="public-spaces"]')).toContainText('Public Test Space');
  });

  test('non-owner cannot modify shared space', async ({ page }) => {
    await loginAsRegularUser(page);
    await page.goto('/dashboard/12345/settings'); // Shared space

    // Verify read-only access
    await expect(page.locator('button:has-text("Delete Space")')).toBeDisabled();
    await expect(page.locator('input[name="space-name"]')).toBeDisabled();
  });

  test('permission denied shows appropriate error', async ({ page }) => {
    await loginAsRegularUser(page);
    await page.goto('/api/v1/searchspaces/12345/delete'); // Try direct API access

    // Should see 403 error
    await expect(page).toHaveURL(/.*403.*/);
  });
});
```

#### 2. **Media Upload & Compression** (High)
```typescript
// tests/e2e/media-compression.spec.ts
test.describe('Media Upload & Compression', () => {
  test('successfully uploads and compresses image', async ({ page }) => {
    await loginAsUser(page);

    // Upload test image
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('fixtures/test-image.jpg');

    // Wait for compression
    await expect(page.locator('[data-testid="compression-progress"]')).toBeVisible();
    await expect(page.locator('[data-testid="compression-success"]')).toBeVisible({ timeout: 30000 });

    // Verify compression metadata displayed
    await expect(page.locator('[data-testid="compression-ratio"]')).toContainText('%');
  });

  test('handles invalid file upload gracefully', async ({ page }) => {
    await loginAsUser(page);

    // Try uploading text file as image
    const fileInput = page.locator('input[type="file"][accept="image/*"]');
    await fileInput.setInputFiles('fixtures/not-an-image.txt');

    // Should show error message
    await expect(page.locator('[data-testid="error-message"]')).toContainText('Invalid or unsupported image');
  });

  test('video compression shows progress', async ({ page }) => {
    await loginAsUser(page);

    const fileInput = page.locator('input[type="file"][accept="video/*"]');
    await fileInput.setInputFiles('fixtures/test-video.mp4');

    // Verify progress bar appears and updates
    await expect(page.locator('[data-testid="compression-progress"]')).toBeVisible();
    const progressBar = page.locator('div[role="progressbar"]');
    await expect(progressBar).toHaveAttribute('aria-valuenow', /[1-9][0-9]*/);
  });
});
```

#### 3. **Community Prompts Usage** (Medium)
```typescript
// tests/e2e/community-prompts.spec.ts
test.describe('Community Prompts', () => {
  test('onboarding shows community prompts', async ({ page }) => {
    await page.goto('/dashboard/onboard');

    // Open prompts selector
    await page.click('[data-testid="community-prompts-button"]');

    // Verify prompts loaded
    await expect(page.locator('[data-testid="prompt-list"]')).toBeVisible();
    await expect(page.locator('[data-testid="prompt-item"]').first()).toBeVisible();
  });

  test('selecting prompt populates system instructions', async ({ page }) => {
    await page.goto('/dashboard/onboard');

    // Select a prompt
    await page.click('[data-testid="community-prompts-button"]');
    await page.click('[data-testid="prompt-item"]:has-text("Code Reviewer")');

    // Verify system instructions populated
    const instructionsField = page.locator('textarea[name="system-instructions"]');
    await expect(instructionsField).toContainText('code reviewer');
  });

  test('prompts categorized correctly', async ({ page }) => {
    await page.goto('/dashboard/settings/prompts');

    // Filter by category
    await page.selectOption('select[name="category"]', 'developer');

    // Verify only developer prompts shown
    const prompts = page.locator('[data-testid="prompt-item"]');
    await expect(prompts).toHaveCount(12); // 12 developer prompts
  });
});
```

### Project Structure
```
tests/
├── e2e/
│   ├── fixtures/
│   │   ├── test-image.jpg
│   │   ├── test-video.mp4
│   │   └── not-an-image.txt
│   ├── helpers/
│   │   ├── auth.ts         # Login helpers
│   │   ├── navigation.ts   # Navigation utilities
│   │   └── assertions.ts   # Custom assertions
│   ├── space-sharing.spec.ts
│   ├── media-compression.spec.ts
│   ├── community-prompts.spec.ts
│   ├── authentication.spec.ts
│   └── search-functionality.spec.ts
├── playwright.config.ts  # Playwright configuration
└── README.md            # E2E testing guide
```

### CI Integration
```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests
on:
  pull_request:
    branches: [main, nightly]
  push:
    branches: [main, nightly]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - name: Install dependencies
        run: npm ci
      - name: Install Playwright browsers
        run: npx playwright install --with-deps
      - name: Run E2E tests
        run: npm run test:e2e
      - name: Upload test results
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: playwright-report/
      - name: Upload failure screenshots
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: test-screenshots
          path: test-results/
```

## Acceptance Criteria
- [ ] Test framework selected and configured (Playwright or Cypress)
- [ ] Minimum 3 core flows tested:
  - [x] Space sharing and permissions
  - [x] Media upload and compression
  - [x] Community prompts usage
- [ ] Tests run successfully on CI
- [ ] Screenshots/videos stored on failed steps
- [ ] Test execution time < 5 minutes for core flows
- [ ] Documentation written for adding new E2E tests
- [ ] Test fixtures checked into repository

## Testing Plan
1. Set up Playwright/Cypress in project
2. Write test for space sharing first (most critical)
3. Verify test runs locally
4. Add media compression tests
5. Add community prompts tests
6. Configure CI integration
7. Run full suite on CI
8. Review and optimize slow tests
9. Document process for team

## Documentation Updates
- [ ] Create `tests/e2e/README.md` with:
  - Setup instructions
  - Running tests locally
  - Writing new tests
  - Debugging failed tests
- [ ] Update main `README.md` with E2E test badge
- [ ] Add testing section to `CONTRIBUTING.md`
- [ ] Document test data fixtures

## Architecture Impact
- **Low Impact**: Tests run in separate pipeline
- **No Production Changes**: Tests validate existing functionality
- **CI Time**: Adds ~5-10 minutes to CI pipeline

## Related Issues/PRs
- Addresses continuous improvement recommendation #2
- Complements existing backend test coverage

## Priority
**Medium-High** - Core flows tested manually but lack automation

## Effort Estimate
- **Framework Setup**: 4-6 hours
- **Core Flow Tests**: 12-16 hours (4-5 hours per flow)
- **CI Integration**: 2-3 hours
- **Documentation**: 2-3 hours
- **Total**: 4-5 days

## References
- [Playwright Documentation](https://playwright.dev/)
- [Cypress Documentation](https://www.cypress.io/)
- [Testing Library Best Practices](https://testing-library.com/docs/queries/about)
- [Current test coverage: Backend APIs, hooks tested; UI flows manual](/)
