# Test Reports & Artifacts

## Table of Contents

1. [CLI Commands](#cli-commands)
2. [Reporter Configuration](#reporter-configuration)
3. [Custom Reporter](#custom-reporter)
4. [Trace Configuration](#trace-configuration)
5. [Screenshot & Video Settings](#screenshot--video-settings)
6. [Artifact Directory Structure](#artifact-directory-structure)
7. [CI Artifact Upload](#ci-artifact-upload)
8. [Decision Guide](#decision-guide)
9. [Anti-Patterns](#anti-patterns)
10. [Troubleshooting](#troubleshooting)

> **When to use**: Configuring test output for debugging, CI dashboards, and team visibility.

## CLI Commands

```bash
# Display last HTML report
npx playwright show-report

# Specify reporter
npx playwright test --reporter=html
npx playwright test --reporter=dot           # minimal CI output
npx playwright test --reporter=line          # one line per test
npx playwright test --reporter=json          # machine-readable
npx playwright test --reporter=junit         # CI integration

# Combine reporters
npx playwright test --reporter=dot,html

# Merge sharded reports
npx playwright merge-reports --reporter=html ./blob-report
```

## Reporter Configuration

### Environment-Based Setup

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  reporter: process.env.CI
    ? [
        ['dot'],
        ['html', { open: 'never' }],
        ['junit', { outputFile: 'results/junit.xml' }],
        ['github'],
      ]
    : [
        ['list'],
        ['html', { open: 'on-failure' }],
      ],
});
```

### Reporter Types

| Reporter | Output | Use Case |
|---|---|---|
| `list` | One line per test | Local development |
| `line` | Single updating line | Local, less verbose |
| `dot` | `.` pass, `F` fail | CI logs |
| `html` | Interactive HTML page | Post-run analysis |
| `json` | Machine-readable JSON | Custom tooling |
| `junit` | JUnit XML | CI platforms |
| `github` | PR annotations | GitHub Actions |
| `blob` | Binary archive | Shard merging |

### JSON Output to File

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  reporter: [
    ['json', { outputFile: 'results/output.json' }],
  ],
});
```

### JUnit Customization

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  reporter: [
    ['junit', {
      outputFile: 'results/junit.xml',
      stripANSIControlSequences: true,
      includeProjectInTestName: true,
    }],
  ],
});
```

## Custom Reporter

Build custom reporters for Slack notifications, database logging, or dashboards.

```typescript
// reporters/notification-reporter.ts
import type {
  FullResult,
  Reporter,
  TestCase,
  TestResult,
} from '@playwright/test/reporter';

class NotificationReporter implements Reporter {
  private passed = 0;
  private failed = 0;
  private skipped = 0;
  private failures: string[] = [];

  onTestEnd(test: TestCase, result: TestResult) {
    switch (result.status) {
      case 'passed':
        this.passed++;
        break;
      case 'failed':
      case 'timedOut':
        this.failed++;
        this.failures.push(`${test.title}: ${result.error?.message?.split('\n')[0]}`);
        break;
      case 'skipped':
        this.skipped++;
        break;
    }
  }

  async onEnd(result: FullResult) {
    const total = this.passed + this.failed + this.skipped;
    const status = this.failed > 0 ? 'FAILED' : 'PASSED';
    const message = [
      `Tests ${status}`,
      `Passed: ${this.passed} | Failed: ${this.failed} | Skipped: ${this.skipped}`,
      `Duration: ${(result.duration / 1000).toFixed(1)}s`,
    ];

    if (this.failures.length > 0) {
      message.push('', 'Failures:');
      this.failures.slice(0, 5).forEach((f) => message.push(`  - ${f}`));
      if (this.failures.length > 5) {
        message.push(`  ...and ${this.failures.length - 5} more`);
      }
    }

    const webhookUrl = process.env.NOTIFICATION_WEBHOOK;
    if (webhookUrl) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      try {
        await fetch(webhookUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: message.join('\n') }),
          signal: controller.signal,
        });
      } catch (error) {
        // Intentionally swallow notifier failures to avoid blocking test completion
        console.warn('Webhook notification failed:', error.message);
      } finally {
        clearTimeout(timeout);
      }
    }
  }
}

export default NotificationReporter;
```

**Register custom reporter:**

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  reporter: [
    ['dot'],
    ['html', { open: 'never' }],
    ['./reporters/notification-reporter.ts'],
  ],
});
```

## Trace Configuration

Traces capture actions, network requests, DOM snapshots, and console logs.

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  retries: process.env.CI ? 2 : 0,
  use: {
    trace: 'on-first-retry',
  },
});
```

### Trace Options

| Value | Behavior | Overhead |
|---|---|---|
| `'off'` | Never records | None |
| `'on'` | Every test | High |
| `'on-first-retry'` | On first retry after failure | Minimal |
| `'retain-on-failure'` | Records all, keeps failures | Medium |
| `'retain-on-first-failure'` | Records all, keeps first failure | Medium |

### Viewing Traces

```bash
# Local trace viewer
npx playwright show-trace results/my-test/trace.zip

# From HTML report (click Traces tab)
npx playwright show-report

# Online viewer: https://trace.playwright.dev
```

## Screenshot & Video Settings

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  use: {
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
});
```

### Video with Custom Size

```typescript
use: {
  video: {
    mode: 'retain-on-failure',
    size: { width: 1280, height: 720 },
  },
},
```

### Screenshot Options

| Value | Captures | Disk Cost |
|---|---|---|
| `'off'` | Never | None |
| `'on'` | Every test | High |
| `'only-on-failure'` | Failed tests | Low |

### Video Options

| Value | Records | Keeps | Disk Cost |
|---|---|---|---|
| `'off'` | Never | — | None |
| `'on'` | Every test | All | Very high |
| `'on-first-retry'` | On retry | Retried | Low |
| `'retain-on-failure'` | Every test | Failed | Medium |

## Artifact Directory Structure

```text
test-results/
├── checkout-test-chromium/
│   ├── trace.zip
│   ├── test-failed-1.png
│   └── video.webm
├── login-test-firefox/
│   ├── trace.zip
│   └── test-failed-1.png
└── junit.xml

playwright-report/
├── index.html
└── data/

blob-report/
└── report-1.zip
```

## CI Artifact Upload

### GitHub Actions

```yaml
- uses: actions/upload-artifact@v4
  if: ${{ !cancelled() }}
  with:
    name: playwright-report
    path: playwright-report/
    retention-days: 14

- uses: actions/upload-artifact@v4
  if: failure()
  with:
    name: test-traces
    path: |
      test-results/**/trace.zip
      test-results/**/*.png
      test-results/**/*.webm
    retention-days: 7
```

## Decision Guide

| Scenario | Reporter Configuration |
|---|---|
| Local development | `[['list'], ['html', { open: 'on-failure' }]]` |
| GitHub Actions | `[['dot'], ['html'], ['github']]` |
| GitLab CI | `[['dot'], ['html'], ['junit']]` |
| Azure DevOps / Jenkins | `[['dot'], ['html'], ['junit']]` |
| Sharded CI | `[['blob'], ['github']]` |
| Custom dashboard | `[['json', { outputFile: '...' }]]` + custom reporter |

| Artifact | When to Collect | Retention | Upload Condition |
|---|---|---|---|
| HTML report | Always | 14 days | `if: ${{ !cancelled() }}` |
| Traces | On failure | 7 days | `if: failure()` |
| Screenshots | On failure | 7 days | `if: failure()` |
| Videos | On failure | 7 days | `if: failure()` |
| JUnit XML | Always | 14 days | `if: ${{ !cancelled() }}` |
| Blob report | Always (sharded) | 1 day | `if: ${{ !cancelled() }}` |

## Anti-Patterns

| Anti-Pattern | Problem | Solution |
|---|---|---|
| No reporter configured | Default `list` only; no persistent report | Configure `html` + CI reporter |
| `trace: 'on'` in CI | Massive artifacts, slow uploads | Use `trace: 'on-first-retry'` |
| `video: 'on'` in CI | Enormous storage, slower tests | Use `video: 'retain-on-failure'` |
| Upload artifacts only on failure | No report when tests pass | Upload with `if: ${{ !cancelled() }}` |
| No retention limits | CI storage fills quickly | Set `retention-days: 7-14` |
| Only `dot` reporter | Cannot drill into failures | Pair `dot` with `html` |
| JUnit to stdout | Interferes with console output | Write to file |
| Blocking `onEnd` in custom reporter | Slow HTTP calls delay pipeline | Use `Promise.race` with timeout |

## Troubleshooting

### Empty HTML Report

Check reporter config. HTML report defaults to `playwright-report/`:

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  reporter: [['html', { outputFolder: 'playwright-report', open: 'never' }]],
});
```

### Traces Too Large

Switch from `trace: 'on'` to `'on-first-retry'` with retries enabled:

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  retries: process.env.CI ? 2 : 0,
  use: {
    trace: 'on-first-retry',
  },
});
```

### JUnit XML Not Recognized

Ensure path matches CI configuration:

```typescript
reporter: [['junit', { outputFile: 'results/junit.xml' }]],
```

```yaml
# GitHub Actions
- uses: dorny/test-reporter@latest
  with:
    path: results/junit.xml
    reporter: java-junit

# Azure DevOps
- task: PublishTestResults@latest
  inputs:
    testResultsFiles: 'results/junit.xml'

# Jenkins
junit 'results/junit.xml'
```

### Empty Merged Report

Use `blob` reporter for sharded runs (not `html`):

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  reporter: process.env.CI
    ? [['blob'], ['dot']]
    : [['html', { open: 'on-failure' }]],
});
```

### Missing Screenshots in Report

Enable screenshots and keep both directories:

```typescript
use: {
  screenshot: 'only-on-failure',
},
```

The HTML report embeds screenshots from `test-results/`. Deleting that directory removes screenshots from the report.
