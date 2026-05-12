---
name: playwright-testing
description: Use when writing Playwright tests, fixing flaky tests, debugging failures, implementing Page Object Model, configuring CI/CD, optimizing performance, mocking APIs, handling authentication or OAuth, testing accessibility (axe-core), file uploads/downloads, date/time mocking, WebSockets, geolocation, permissions, multi-tab/popup flows, mobile/responsive layouts, touch gestures, GraphQL, error handling, offline mode, multi-user collaboration, third-party services (payments, email verification), console error monitoring, global setup/teardown, test annotations (skip, fixme, slow), test tags (@smoke, @fast, @critical, filtering with --grep), project dependencies, security testing (XSS, CSRF, auth), performance budgets (Web Vitals, Lighthouse), iframes, component testing, canvas/WebGL, service workers/PWA, test coverage, i18n/localization, Electron apps, or browser extension testing. Covers E2E, component, API, visual, accessibility, security, Electron, and extension testing.
---

# Playwright Testing

This skill provides comprehensive guidance for all aspects of Playwright test development, from writing new tests to debugging and maintaining existing test suites.

## Activity-Based Reference Guide

Consult these references based on what you're doing:

### Writing New Tests

**When to use**: Creating new test files, writing test cases, implementing test scenarios

| Activity                            | Reference Files                                                                                                                               |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **Writing E2E tests**               | [test-suite-structure.md](core/test-suite-structure.md), [locators.md](core/locators.md), [assertions-waiting.md](core/assertions-waiting.md) |
| **Writing component tests**         | [component-testing.md](testing-patterns/component-testing.md), [test-suite-structure.md](core/test-suite-structure.md)                        |
| **Writing API tests**               | [api-testing.md](testing-patterns/api-testing.md), [test-suite-structure.md](core/test-suite-structure.md)                                    |
| **Writing GraphQL tests**           | [graphql-testing.md](testing-patterns/graphql-testing.md), [api-testing.md](testing-patterns/api-testing.md)                                  |
| **Writing visual regression tests** | [visual-regression.md](testing-patterns/visual-regression.md), [canvas-webgl.md](testing-patterns/canvas-webgl.md)                            |
| **Structuring test code with POM**  | [page-object-model.md](core/page-object-model.md), [test-suite-structure.md](core/test-suite-structure.md)                                    |
| **Setting up test data/fixtures**   | [fixtures-hooks.md](core/fixtures-hooks.md), [test-data.md](core/test-data.md)                                                                |
| **Handling authentication**         | [authentication.md](advanced/authentication.md), [authentication-flows.md](advanced/authentication-flows.md)                                  |
| **Testing date/time features**      | [clock-mocking.md](advanced/clock-mocking.md)                                                                                                 |
| **Testing file upload/download**    | [file-operations.md](testing-patterns/file-operations.md), [file-upload-download.md](testing-patterns/file-upload-download.md)                |
| **Testing forms/validation**        | [forms-validation.md](testing-patterns/forms-validation.md)                                                                                   |
| **Testing drag and drop**           | [drag-drop.md](testing-patterns/drag-drop.md)                                                                                                 |
| **Testing accessibility**           | [accessibility.md](testing-patterns/accessibility.md)                                                                                         |
| **Testing security (XSS, CSRF)**    | [security-testing.md](testing-patterns/security-testing.md)                                                                                   |
| **Using test annotations**          | [annotations.md](core/annotations.md)                                                                                                         |
| **Using test tags**                 | [test-tags.md](core/test-tags.md)                                                                                                             |
| **Testing iframes**                 | [iframes.md](browser-apis/iframes.md)                                                                                                         |
| **Testing canvas/WebGL**            | [canvas-webgl.md](testing-patterns/canvas-webgl.md)                                                                                           |
| **Internationalization (i18n)**     | [i18n.md](testing-patterns/i18n.md)                                                                                                           |
| **Testing Electron apps**           | [electron.md](testing-patterns/electron.md)                                                                                                   |
| **Testing browser extensions**      | [browser-extensions.md](testing-patterns/browser-extensions.md)                                                                               |

### Mobile & Responsive Testing

**When to use**: Testing mobile devices, touch interactions, responsive layouts

| Activity                        | Reference Files                                                                  |
| ------------------------------- | -------------------------------------------------------------------------------- |
| **Device emulation**            | [mobile-testing.md](advanced/mobile-testing.md)                                  |
| **Touch gestures (swipe, tap)** | [mobile-testing.md](advanced/mobile-testing.md)                                  |
| **Viewport/breakpoint testing** | [mobile-testing.md](advanced/mobile-testing.md)                                  |
| **Mobile-specific UI**          | [mobile-testing.md](advanced/mobile-testing.md), [locators.md](core/locators.md) |

### Real-Time & Browser APIs

**When to use**: Testing WebSockets, geolocation, permissions, multi-tab flows

| Activity                        | Reference Files                                                                          |
| ------------------------------- | ---------------------------------------------------------------------------------------- |
| **WebSocket/real-time testing** | [websockets.md](browser-apis/websockets.md)                                              |
| **Geolocation mocking**         | [browser-apis.md](browser-apis/browser-apis.md)                                          |
| **Permission handling**         | [browser-apis.md](browser-apis/browser-apis.md)                                          |
| **Clipboard testing**           | [browser-apis.md](browser-apis/browser-apis.md)                                          |
| **Camera/microphone mocking**   | [browser-apis.md](browser-apis/browser-apis.md)                                          |
| **Multi-tab/popup flows**       | [multi-context.md](advanced/multi-context.md)                                            |
| **OAuth popup handling**        | [third-party.md](advanced/third-party.md), [multi-context.md](advanced/multi-context.md) |

### Debugging & Troubleshooting

**When to use**: Test failures, element not found, timeouts, unexpected behavior

| Activity                                          | Reference Files                                                                                                                                |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Debugging test failures**                       | [debugging.md](debugging/debugging.md), [assertions-waiting.md](core/assertions-waiting.md)                                                    |
| **Fixing flaky tests**                            | [flaky-tests.md](debugging/flaky-tests.md), [debugging.md](debugging/debugging.md), [assertions-waiting.md](core/assertions-waiting.md)        |
| **Debugging flaky parallel runs**                 | [flaky-tests.md](debugging/flaky-tests.md), [performance.md](infrastructure-ci-cd/performance.md), [fixtures-hooks.md](core/fixtures-hooks.md) |
| **Ensuring test isolation / avoiding state leak** | [flaky-tests.md](debugging/flaky-tests.md), [fixtures-hooks.md](core/fixtures-hooks.md), [performance.md](infrastructure-ci-cd/performance.md) |
| **Fixing selector issues**                        | [locators.md](core/locators.md), [debugging.md](debugging/debugging.md)                                                                        |
| **Investigating timeout issues**                  | [assertions-waiting.md](core/assertions-waiting.md), [debugging.md](debugging/debugging.md)                                                    |
| **Using trace viewer**                            | [debugging.md](debugging/debugging.md)                                                                                                         |
| **Debugging race conditions**                     | [flaky-tests.md](debugging/flaky-tests.md), [debugging.md](debugging/debugging.md), [assertions-waiting.md](core/assertions-waiting.md)        |
| **Debugging console/JS errors**                   | [console-errors.md](debugging/console-errors.md), [debugging.md](debugging/debugging.md)                                                       |

### Error & Edge Case Testing

**When to use**: Testing error states, offline mode, network failures, validation

| Activity                       | Reference Files                                                                                       |
| ------------------------------ | ----------------------------------------------------------------------------------------------------- |
| **Error boundary testing**     | [error-testing.md](debugging/error-testing.md)                                                        |
| **Network failure simulation** | [error-testing.md](debugging/error-testing.md), [network-advanced.md](advanced/network-advanced.md)   |
| **Offline mode testing**       | [error-testing.md](debugging/error-testing.md), [service-workers.md](browser-apis/service-workers.md) |
| **Service worker testing**     | [service-workers.md](browser-apis/service-workers.md)                                                 |
| **Loading state testing**      | [error-testing.md](debugging/error-testing.md)                                                        |
| **Form validation testing**    | [error-testing.md](debugging/error-testing.md)                                                        |

### Multi-User & Collaboration Testing

**When to use**: Testing features involving multiple users, roles, or real-time collaboration

| Activity                       | Reference Files                                                                      |
| ------------------------------ | ------------------------------------------------------------------------------------ |
| **Multiple users in one test** | [multi-user.md](advanced/multi-user.md)                                              |
| **Real-time collaboration**    | [multi-user.md](advanced/multi-user.md), [websockets.md](browser-apis/websockets.md) |
| **Role-based access testing**  | [multi-user.md](advanced/multi-user.md)                                              |
| **Concurrent action testing**  | [multi-user.md](advanced/multi-user.md)                                              |

### Architecture Decisions

**When to use**: Choosing test patterns, deciding between approaches, planning test architecture

| Activity                     | Reference Files                                           |
| ---------------------------- | --------------------------------------------------------- |
| **POM vs fixtures decision** | [pom-vs-fixtures.md](architecture/pom-vs-fixtures.md)     |
| **Test type selection**      | [test-architecture.md](architecture/test-architecture.md) |
| **Mock vs real services**    | [when-to-mock.md](architecture/when-to-mock.md)           |
| **Test suite structure**     | [test-suite-structure.md](core/test-suite-structure.md)   |

### Framework-Specific Testing

**When to use**: Testing React or Next.js applications

| Activity                  | Reference Files                     |
| ------------------------- | ----------------------------------- |
| **Testing React apps**    | [react.md](frameworks/react.md)     |
| **Testing Next.js apps**  | [nextjs.md](frameworks/nextjs.md)   |

### Refactoring & Maintenance

**When to use**: Improving existing tests, code review, reducing duplication

| Activity                             | Reference Files                                                                                            |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| **Refactoring to Page Object Model** | [page-object-model.md](core/page-object-model.md), [test-suite-structure.md](core/test-suite-structure.md) |
| **Improving test organization**      | [test-suite-structure.md](core/test-suite-structure.md), [page-object-model.md](core/page-object-model.md) |
| **Extracting common setup/teardown** | [fixtures-hooks.md](core/fixtures-hooks.md)                                                                |
| **Replacing brittle selectors**      | [locators.md](core/locators.md)                                                                            |
| **Removing explicit waits**          | [assertions-waiting.md](core/assertions-waiting.md)                                                        |
| **Creating test data factories**     | [test-data.md](core/test-data.md)                                                                          |
| **Configuration setup**              | [configuration.md](core/configuration.md)                                                                  |

### Infrastructure & Configuration

**When to use**: Setting up projects, configuring CI/CD, optimizing performance

| Activity                                | Reference Files                                                                                                          |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **Configuring Playwright project**      | [configuration.md](core/configuration.md), [projects-dependencies.md](core/projects-dependencies.md)                     |
| **Setting up CI/CD pipelines**          | [ci-cd.md](infrastructure-ci-cd/ci-cd.md), [github-actions.md](infrastructure-ci-cd/github-actions.md)                   |
| **GitHub Actions setup**                | [github-actions.md](infrastructure-ci-cd/github-actions.md)                                                              |
| **GitLab CI setup**                     | [gitlab.md](infrastructure-ci-cd/gitlab.md)                                                                              |
| **Other CI providers**                  | [other-providers.md](infrastructure-ci-cd/other-providers.md)                                                            |
| **Docker/container setup**              | [docker.md](infrastructure-ci-cd/docker.md)                                                                              |
| **Global setup & teardown**             | [global-setup.md](core/global-setup.md)                                                                                  |
| **Project dependencies**                | [projects-dependencies.md](core/projects-dependencies.md)                                                                |
| **Optimizing test performance**         | [performance.md](infrastructure-ci-cd/performance.md), [test-suite-structure.md](core/test-suite-structure.md)           |
| **Configuring parallel execution**      | [parallel-sharding.md](infrastructure-ci-cd/parallel-sharding.md), [performance.md](infrastructure-ci-cd/performance.md) |
| **Isolating test data between workers** | [fixtures-hooks.md](core/fixtures-hooks.md), [performance.md](infrastructure-ci-cd/performance.md)                       |
| **Test coverage**                       | [test-coverage.md](infrastructure-ci-cd/test-coverage.md)                                                                |
| **Test reporting/artifacts**            | [reporting.md](infrastructure-ci-cd/reporting.md)                                                                        |

### Advanced Patterns

**When to use**: Complex scenarios, API mocking, network interception

| Activity                             | Reference Files                                                                                              |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| **Mocking API responses**            | [test-suite-structure.md](core/test-suite-structure.md), [network-advanced.md](advanced/network-advanced.md) |
| **Network interception**             | [network-advanced.md](advanced/network-advanced.md), [assertions-waiting.md](core/assertions-waiting.md)     |
| **GraphQL mocking**                  | [network-advanced.md](advanced/network-advanced.md)                                                          |
| **HAR recording/playback**           | [network-advanced.md](advanced/network-advanced.md)                                                          |
| **Custom fixtures**                  | [fixtures-hooks.md](core/fixtures-hooks.md)                                                                  |
| **Advanced waiting strategies**      | [assertions-waiting.md](core/assertions-waiting.md)                                                          |
| **OAuth/SSO mocking**                | [third-party.md](advanced/third-party.md), [multi-context.md](advanced/multi-context.md)                     |
| **Payment gateway mocking**          | [third-party.md](advanced/third-party.md)                                                                    |
| **Email/SMS verification mocking**   | [third-party.md](advanced/third-party.md)                                                                    |
| **Failing on console errors**        | [console-errors.md](debugging/console-errors.md)                                                             |
| **Security testing (XSS, CSRF)**     | [security-testing.md](testing-patterns/security-testing.md)                                                  |
| **Performance budgets & Web Vitals** | [performance-testing.md](testing-patterns/performance-testing.md)                                            |
| **Lighthouse integration**           | [performance-testing.md](testing-patterns/performance-testing.md)                                            |
| **Test annotations (skip, fixme)**   | [annotations.md](core/annotations.md)                                                                        |
| **Test tags (@smoke, @fast)**        | [test-tags.md](core/test-tags.md)                                                                            |
| **Test steps for reporting**         | [annotations.md](core/annotations.md)                                                                        |

## Quick Decision Tree

```
What are you doing?
│
├─ Writing a new test?
│  ├─ E2E test → core/test-suite-structure.md, core/locators.md, core/assertions-waiting.md
│  ├─ Component test → testing-patterns/component-testing.md
│  ├─ API test → testing-patterns/api-testing.md, core/test-suite-structure.md
│  ├─ GraphQL test → testing-patterns/graphql-testing.md
│  ├─ Visual regression → testing-patterns/visual-regression.md
│  ├─ Visual/canvas test → testing-patterns/canvas-webgl.md, core/test-suite-structure.md
│  ├─ Accessibility test → testing-patterns/accessibility.md
│  ├─ Mobile/responsive test → advanced/mobile-testing.md
│  ├─ i18n/locale test → testing-patterns/i18n.md
│  ├─ Electron app test → testing-patterns/electron.md
│  ├─ Browser extension test → testing-patterns/browser-extensions.md
│  ├─ Multi-user test → advanced/multi-user.md
│  ├─ Form validation test → testing-patterns/forms-validation.md
│  └─ Drag and drop test → testing-patterns/drag-drop.md
│
├─ Testing specific features?
│  ├─ File upload/download → testing-patterns/file-operations.md, testing-patterns/file-upload-download.md
│  ├─ Date/time dependent → advanced/clock-mocking.md
│  ├─ WebSocket/real-time → browser-apis/websockets.md
│  ├─ Geolocation/permissions → browser-apis/browser-apis.md
│  ├─ OAuth/SSO mocking → advanced/third-party.md, advanced/multi-context.md
│  ├─ Payments/email/SMS → advanced/third-party.md
│  ├─ iFrames → browser-apis/iframes.md
│  ├─ Canvas/WebGL/charts → testing-patterns/canvas-webgl.md
│  ├─ Service workers/PWA → browser-apis/service-workers.md
│  ├─ i18n/localization → testing-patterns/i18n.md
│  ├─ Security (XSS, CSRF) → testing-patterns/security-testing.md
│  └─ Performance/Web Vitals → testing-patterns/performance-testing.md
│
├─ Architecture decisions?
│  ├─ POM vs fixtures → architecture/pom-vs-fixtures.md
│  ├─ Test type selection → architecture/test-architecture.md
│  ├─ Mock vs real services → architecture/when-to-mock.md
│  └─ Test suite structure → core/test-suite-structure.md
│
├─ Framework-specific testing?
│  ├─ React app → frameworks/react.md
│  └─ Next.js app → frameworks/nextjs.md
│
├─ Authentication testing?
│  ├─ Basic auth patterns → advanced/authentication.md
│  └─ Complex flows (MFA, reset) → advanced/authentication-flows.md
│
├─ Test is failing/flaky?
│  ├─ Flaky test investigation → debugging/flaky-tests.md
│  ├─ Element not found → core/locators.md, debugging/debugging.md
│  ├─ Timeout issues → core/assertions-waiting.md, debugging/debugging.md
│  ├─ Race conditions → debugging/flaky-tests.md, debugging/debugging.md
│  ├─ Flaky only with multiple workers → debugging/flaky-tests.md, infrastructure-ci-cd/performance.md
│  ├─ State leak / isolation → debugging/flaky-tests.md, core/fixtures-hooks.md
│  ├─ Console/JS errors → debugging/console-errors.md, debugging/debugging.md
│  └─ General debugging → debugging/debugging.md
│
├─ Testing error scenarios?
│  ├─ Network failures → debugging/error-testing.md, advanced/network-advanced.md
│  ├─ Offline (unexpected) → debugging/error-testing.md
│  ├─ Offline-first/PWA → browser-apis/service-workers.md
│  ├─ Error boundaries → debugging/error-testing.md
│  └─ Form validation → testing-patterns/forms-validation.md, debugging/error-testing.md
│
├─ Refactoring existing code?
│  ├─ Implementing POM → core/page-object-model.md
│  ├─ Improving selectors → core/locators.md
│  ├─ Extracting fixtures → core/fixtures-hooks.md
│  ├─ Creating data factories → core/test-data.md
│  └─ Configuration setup → core/configuration.md
│
├─ Setting up infrastructure?
│  ├─ CI/CD → infrastructure-ci-cd/ci-cd.md
│  ├─ GitHub Actions → infrastructure-ci-cd/github-actions.md
│  ├─ GitLab CI → infrastructure-ci-cd/gitlab.md
│  ├─ Other CI providers → infrastructure-ci-cd/other-providers.md
│  ├─ Docker/containers → infrastructure-ci-cd/docker.md
│  ├─ Sharding/parallel → infrastructure-ci-cd/parallel-sharding.md
│  ├─ Reporting/artifacts → infrastructure-ci-cd/reporting.md
│  ├─ Global setup/teardown → core/global-setup.md
│  ├─ Project dependencies → core/projects-dependencies.md
│  ├─ Test performance → infrastructure-ci-cd/performance.md
│  ├─ Test coverage → infrastructure-ci-cd/test-coverage.md
│  └─ Project config → core/configuration.md, core/projects-dependencies.md
│
├─ Organizing tests?
│  ├─ Skip/fixme/slow tests → core/annotations.md
│  ├─ Test tags (@smoke, @fast) → core/test-tags.md
│  ├─ Filtering tests (--grep) → core/test-tags.md
│  ├─ Test steps → core/annotations.md
│  └─ Conditional execution → core/annotations.md
│
└─ Running subset of tests?
   ├─ By tag (@smoke, @critical) → core/test-tags.md
   ├─ Exclude slow/flaky tests → core/test-tags.md
   ├─ PR vs nightly tests → core/test-tags.md, infrastructure-ci-cd/ci-cd.md
   └─ Project-specific filtering → core/test-tags.md, core/configuration.md
```

## Test Validation Loop

After writing or modifying tests:

1. **Run tests**: `npx playwright test --reporter=list`
2. **If tests fail**:
   - Review error output and trace (`npx playwright show-trace`)
   - Fix locators, waits, or assertions
   - Re-run tests
3. **Only proceed when all tests pass**
4. **Run multiple times** for critical tests: `npx playwright test --repeat-each=5`
