# Container-Based Testing

## Table of Contents

1. [Patterns](#patterns)
2. [Decision Guide](#decision-guide)
3. [Anti-Patterns](#anti-patterns)
4. [Troubleshooting](#troubleshooting)

> **When to use**: Running tests in containers for reproducible environments, CI pipelines, or consistent browser versions across team machines.

## Patterns

### Official Image Usage

Run tests without building a custom image:

```bash
docker run --rm \
  -v $(pwd):/app \
  -w /app \
  -e CI=true \
  -e BASE_URL=http://host.docker.internal:3000 \
  mcr.microsoft.com/playwright:v1.48.0-noble \
  bash -c "npm ci && npx playwright test"
```

Extract reports with bind mounts:

```bash
docker run --rm \
  -v $(pwd):/app \
  -v $(pwd)/playwright-report:/app/playwright-report \
  -v $(pwd)/test-results:/app/test-results \
  -w /app \
  mcr.microsoft.com/playwright:v1.48.0-noble \
  bash -c "npm ci && npx playwright test"
```

### Custom Dockerfile

Build a custom image when you need additional dependencies or pre-installed packages:

```dockerfile
FROM mcr.microsoft.com/playwright:v1.48.0-noble

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

CMD ["npx", "playwright", "test"]
```

Chromium-only slim image:

```dockerfile
FROM node:latest-slim

RUN npx playwright install --with-deps chromium

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

CMD ["npx", "playwright", "test", "--project=chromium"]
```

### Docker Compose Stack

Full application stack with database, cache, and test runner:

```yaml
services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=test
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/test
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:latest-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: test
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    tmpfs:
      - /var/lib/postgresql/data

  e2e:
    image: mcr.microsoft.com/playwright:v1.48.0-noble
    working_dir: /app
    volumes:
      - .:/app
      - /app/node_modules
    environment:
      - CI=true
      - BASE_URL=http://app:3000
    depends_on:
      - app
    command: bash -c "npm ci && npx playwright test"
    profiles:
      - test
```

Run commands:

```bash
docker compose --profile test up --abort-on-container-exit --exit-code-from e2e

docker compose --profile test down -v
```

### CI Container Jobs

**GitHub Actions:**

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    container:
      image: mcr.microsoft.com/playwright:v1.48.0-noble
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx playwright test
        env:
          HOME: /root
```

**GitLab CI:**

```yaml
test:
  image: mcr.microsoft.com/playwright:v1.48.0-noble
  script:
    - npm ci
    - npx playwright test
```

**Jenkins:**

```groovy
pipeline {
    agent {
        docker {
            image 'mcr.microsoft.com/playwright:v1.48.0-noble'
            args '-u root'
        }
    }
    stages {
        stage('Test') {
            steps {
                sh 'npm ci'
                sh 'npx playwright test'
            }
        }
    }
}
```

### Dev Container Setup

VS Code Dev Container or GitHub Codespaces configuration:

```json
{
  "name": "Playwright Dev",
  "image": "mcr.microsoft.com/playwright:v1.48.0-noble",
  "features": {
    "ghcr.io/devcontainers/features/node:latest": {
      "version": "20"
    }
  },
  "postCreateCommand": "npm ci",
  "customizations": {
    "vscode": {
      "extensions": ["ms-playwright.playwright"]
    }
  },
  "forwardPorts": [3000, 9323],
  "remoteUser": "root"
}
```

## Decision Guide

| Scenario | Approach |
|---|---|
| Simple CI pipeline | Official image as CI container |
| Tests need database + cache | Docker Compose with app, db, e2e services |
| Team needs identical environments | Dev Container or custom Dockerfile |
| Only testing Chromium | Slim image with `install --with-deps chromium` |
| Cross-browser testing | Official image (all browsers pre-installed) |
| Local development | Run directly on host for faster iteration |

## Anti-Patterns

| Anti-Pattern | Problem | Solution |
|---|---|---|
| Installing browsers at runtime | Wastes 60-90 seconds per run | Use official image or bake browsers into custom image |
| Running as non-root without sandbox config | Chromium sandbox permission errors | Run as root or disable sandbox |
| Bind-mounting `node_modules` from host | Platform-specific binary crashes | Use anonymous volume: `-v /app/node_modules` |
| No health checks on dependent services | Tests start before database ready | Add `healthcheck` with `depends_on: condition: service_healthy` |
| Building application inside Playwright container | Large image, slow builds | Separate app and e2e containers |

## Troubleshooting

### "browserType.launch: Executable doesn't exist"

Playwright version mismatch with Docker image. Ensure `@playwright/test` version matches image tag:

```bash
npm ls @playwright/test
docker pull mcr.microsoft.com/playwright:v<matching-version>-noble
```

### "net::ERR_CONNECTION_REFUSED" in docker-compose

Tests trying to reach `localhost` instead of service name. Configure `baseURL`:

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
  },
});
```

```yaml
e2e:
  environment:
    - BASE_URL=http://app:3000
```

### Permission denied on mounted volumes

Match user IDs or run as root:

```bash
docker run --rm -u $(id -u):$(id -g) \
  -v $(pwd):/app -w /app \
  mcr.microsoft.com/playwright:v1.48.0-noble \
  npx playwright test
```

### Slow container tests on macOS/Windows

Docker Desktop I/O overhead. Copy files instead of mounting:

```dockerfile
FROM mcr.microsoft.com/playwright:v1.48.0-noble
WORKDIR /app
COPY . .
RUN npm ci
CMD ["npx", "playwright", "test"]
```

Or use delegated mount:

```bash
docker run --rm \
  -v $(pwd):/app:delegated \
  -w /app \
  mcr.microsoft.com/playwright:v1.48.0-noble \
  bash -c "npm ci && npx playwright test"
```
