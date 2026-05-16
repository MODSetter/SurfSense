# CI: CircleCI, Azure DevOps, and Jenkins

> **When to use**: Running Playwright tests in CI platforms other than GitHub Actions or GitLab.

## Table of Contents

1. [Common Commands](#common-commands)
2. [Jenkins](#jenkins)
3. [CircleCI](#circleci)
4. [Azure DevOps](#azure-devops)
5. [JUnit Reporter Config](#junit-reporter-config)
6. [Platform Comparison](#platform-comparison)
7. [Troubleshooting](#troubleshooting)
8. [Anti-Patterns](#anti-patterns)

---

## Common Commands

```bash
npx playwright install --with-deps    # browsers + OS dependencies
npx playwright test --shard=1/4       # parallel sharding
npx playwright merge-reports ./blob-report  # combine shard results
npx playwright test --reporter=dot,html     # multiple reporters
```

## Jenkins

### Declarative Pipeline

```groovy
// Jenkinsfile
pipeline {
    agent {
        docker {
            image 'mcr.microsoft.com/playwright:v1.48.0-noble'
            args '-u root'
        }
    }

    environment {
        CI = 'true'
        HOME = '/root'
        npm_config_cache = "${WORKSPACE}/.npm"
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {
        stage('Install') {
            steps {
                sh 'npm ci'
            }
        }

        stage('Test') {
            steps {
                sh 'npx playwright test'
            }
            post {
                always {
                    junit allowEmptyResults: true,
                         testResults: 'results/junit.xml'
                    archiveArtifacts artifacts: 'pw-report/**',
                                     allowEmptyArchive: true
                    archiveArtifacts artifacts: 'results/**',
                                     allowEmptyArchive: true
                }
            }
        }
    }

    post {
        failure {
            echo 'Tests failed!'
        }
        cleanup {
            cleanWs()
        }
    }
}
```

### Parallel Shards

```groovy
// Jenkinsfile (sharded)
pipeline {
    agent none

    environment {
        CI = 'true'
        HOME = '/root'
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
    }

    stages {
        stage('Test') {
            parallel {
                stage('Shard 1') {
                    agent {
                        docker {
                            image 'mcr.microsoft.com/playwright:v1.48.0-noble'
                            args '-u root'
                        }
                    }
                    steps {
                        sh 'npm ci'
                        sh 'npx playwright test --shard=1/4'
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: 'blob-report/**',
                                             allowEmptyArchive: true
                        }
                    }
                }
                stage('Shard 2') {
                    agent {
                        docker {
                            image 'mcr.microsoft.com/playwright:v1.48.0-noble'
                            args '-u root'
                        }
                    }
                    steps {
                        sh 'npm ci'
                        sh 'npx playwright test --shard=2/4'
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: 'blob-report/**',
                                             allowEmptyArchive: true
                        }
                    }
                }
                stage('Shard 3') {
                    agent {
                        docker {
                            image 'mcr.microsoft.com/playwright:v1.48.0-noble'
                            args '-u root'
                        }
                    }
                    steps {
                        sh 'npm ci'
                        sh 'npx playwright test --shard=3/4'
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: 'blob-report/**',
                                             allowEmptyArchive: true
                        }
                    }
                }
                stage('Shard 4') {
                    agent {
                        docker {
                            image 'mcr.microsoft.com/playwright:v1.48.0-noble'
                            args '-u root'
                        }
                    }
                    steps {
                        sh 'npm ci'
                        sh 'npx playwright test --shard=4/4'
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: 'blob-report/**',
                                             allowEmptyArchive: true
                        }
                    }
                }
            }
        }
    }
}
```

## CircleCI

### Basic Pipeline

```yaml
# .circleci/config.yml
version: 2.1

executors:
  pw:
    docker:
      - image: mcr.microsoft.com/playwright:v1.48.0-noble
    working_directory: ~/app

jobs:
  install:
    executor: pw
    steps:
      - checkout
      - restore_cache:
          keys:
            - deps-{{ checksum "package-lock.json" }}
      - run: npm ci
      - save_cache:
          key: deps-{{ checksum "package-lock.json" }}
          paths:
            - node_modules
      - persist_to_workspace:
          root: .
          paths:
            - node_modules

  test:
    executor: pw
    parallelism: 4
    steps:
      - checkout
      - attach_workspace:
          at: .
      - run:
          name: Run tests
          command: |
            npx playwright test --shard=$((CIRCLE_NODE_INDEX + 1))/$CIRCLE_NODE_TOTAL
      - store_artifacts:
          path: pw-report
          destination: pw-report
      - store_artifacts:
          path: results
          destination: results
      - store_test_results:
          path: results/junit.xml

workflows:
  test:
    jobs:
      - install
      - test:
          requires:
            - install
```

### Using Orbs

```yaml
# .circleci/config.yml
version: 2.1

orbs:
  node: circleci/node@latest

executors:
  pw:
    docker:
      - image: mcr.microsoft.com/playwright:v1.48.0-noble

jobs:
  e2e:
    executor: pw
    parallelism: 4
    steps:
      - checkout
      - node/install-packages
      - run:
          name: Run tests
          command: npx playwright test --shard=$((CIRCLE_NODE_INDEX + 1))/$CIRCLE_NODE_TOTAL
      - store_artifacts:
          path: pw-report
      - store_test_results:
          path: results/junit.xml

workflows:
  main:
    jobs:
      - e2e
```

## Azure DevOps

### Basic Pipeline

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include:
      - main

pr:
  branches:
    include:
      - main

pool:
  vmImage: "ubuntu-latest"

variables:
  CI: "true"
  npm_config_cache: $(Pipeline.Workspace)/.npm

steps:
  - task: NodeTool@0
    inputs:
      versionSpec: "20.x"
    displayName: "Install Node.js"

  - task: Cache@2
    inputs:
      key: 'npm | "$(Agent.OS)" | package-lock.json'
      restoreKeys: |
        npm | "$(Agent.OS)"
      path: $(npm_config_cache)
    displayName: "Cache npm"

  - script: npm ci
    displayName: "Install dependencies"

  - script: npx playwright install --with-deps
    displayName: "Install browsers"

  - script: npx playwright test
    displayName: "Run tests"

  - task: PublishTestResults@2
    condition: always()
    inputs:
      testResultsFormat: "JUnit"
      testResultsFiles: "results/junit.xml"
      mergeTestResults: true
      testRunTitle: "E2E Tests"
    displayName: "Publish results"

  - task: PublishPipelineArtifact@1
    condition: always()
    inputs:
      targetPath: pw-report
      artifact: pw-report
      publishLocation: "pipeline"
    displayName: "Upload report"
```

### With Sharding

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include:
      - main

pr:
  branches:
    include:
      - main

variables:
  CI: "true"

stages:
  - stage: Test
    jobs:
      - job: E2E
        pool:
          vmImage: "ubuntu-latest"
        strategy:
          matrix:
            shard1:
              SHARD: "1/4"
            shard2:
              SHARD: "2/4"
            shard3:
              SHARD: "3/4"
            shard4:
              SHARD: "4/4"
        steps:
          - task: NodeTool@0
            inputs:
              versionSpec: "20.x"

          - script: npm ci
            displayName: "Install dependencies"

          - script: npx playwright install --with-deps
            displayName: "Install browsers"

          - script: npx playwright test --shard=$(SHARD)
            displayName: "Run tests (shard $(SHARD))"

          - task: PublishPipelineArtifact@1
            condition: always()
            inputs:
              targetPath: blob-report
              artifact: blob-report-$(System.JobPositionInPhase)
            displayName: "Upload blob report"

  - stage: Report
    dependsOn: Test
    condition: always()
    jobs:
      - job: MergeReports
        pool:
          vmImage: "ubuntu-latest"
        steps:
          - task: NodeTool@0
            inputs:
              versionSpec: "20.x"

          - script: npm ci
            displayName: "Install dependencies"

          - task: DownloadPipelineArtifact@2
            inputs:
              patterns: "blob-report-*/**"
              path: all-blob-reports
            displayName: "Download blob reports"

          - script: npx playwright merge-reports --reporter=html ./all-blob-reports
            displayName: "Merge reports"

          - task: PublishPipelineArtifact@1
            inputs:
              targetPath: pw-report
              artifact: pw-report
            displayName: "Upload merged report"
```

## JUnit Reporter Config

All platforms benefit from JUnit output for native test result display:

```typescript
// playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  reporter: process.env.CI
    ? [
        ["dot"],
        ["html", { open: "never" }],
        ["junit", { outputFile: "results/junit.xml" }],
      ]
    : [["html", { open: "on-failure" }]],
});
```

## Platform Comparison

| Feature           | CircleCI                                        | Azure DevOps                     | Jenkins                |
| ----------------- | ----------------------------------------------- | -------------------------------- | ---------------------- |
| Docker support    | `docker:` executor                              | `vmImage` or container jobs      | Docker Pipeline plugin |
| Parallelism       | `parallelism: N` + `CIRCLE_NODE_INDEX`          | `strategy.matrix`                | `parallel` stages      |
| Artifact upload   | `store_artifacts`                               | `PublishPipelineArtifact@1`      | `archiveArtifacts`     |
| JUnit integration | `store_test_results`                            | `PublishTestResults@2`           | `junit` step           |
| Shard variable    | `$((CIRCLE_NODE_INDEX + 1))/$CIRCLE_NODE_TOTAL` | Define in matrix: `SHARD: '1/4'` | Hardcode per stage     |
| Cache key         | `checksum "package-lock.json"`                  | `Cache@2` with key template      | `stash`/`unstash`      |
| Secrets           | Context + env variables                         | Variable groups                  | Credentials plugin     |

## Troubleshooting

### Jenkins: "Browser closed unexpectedly"

Running as non-root in container causes sandbox issues.

```groovy
agent {
    docker {
        image 'mcr.microsoft.com/playwright:v1.48.0-noble'
        args '-u root'
    }
}
environment {
    HOME = '/root'
}
```

### CircleCI: "Executable doesn't exist"

Image version mismatch with `@playwright/test` version. Use `latest` tag or match versions:

```yaml
docker:
  - image: mcr.microsoft.com/playwright:v1.48.0-noble
```

### Azure DevOps: Test results not showing

Missing JUnit reporter or `PublishTestResults@2` task:

```typescript
reporter: [['junit', { outputFile: 'results/junit.xml' }]],
```

```yaml
- task: PublishTestResults@2
  condition: always()
  inputs:
    testResultsFormat: "JUnit"
    testResultsFiles: "results/junit.xml"
```

### Shard index off by one

CircleCI's `CIRCLE_NODE_INDEX` is 0-based, Playwright's `--shard` is 1-based:

```yaml
# CircleCI - add 1
command: npx playwright test --shard=$((CIRCLE_NODE_INDEX + 1))/$CIRCLE_NODE_TOTAL
```

## Anti-Patterns

| Anti-Pattern                        | Problem                                   | Solution                                             |
| ----------------------------------- | ----------------------------------------- | ---------------------------------------------------- |
| Missing `--with-deps` on bare metal | OS libs missing, browser launch fails     | Use Playwright Docker image or `--with-deps`         |
| No JUnit reporter                   | CI can't display test results             | Add `['junit', { outputFile: 'results/junit.xml' }]` |
| No job timeout                      | Hung tests consume resources indefinitely | Set explicit timeout (20-30 min)                     |
| No artifact upload on success       | Can't verify passing results              | Always upload reports (`condition: always()`)        |
| Non-root in container without setup | Permission errors on browser binaries     | Run as root or configure permissions                 |
| Hardcoded shard count               | Must update multiple places               | Use CI-native variables                              |
