# SurfSense CI/CD Reference Guide

This document explains how SurfSense's CI/CD system works and how it integrates with the Makefile targets.

## CI/CD Architecture

SurfSense uses GitHub Actions for continuous integration and continuous deployment. The CI/CD pipeline is designed to:

1. Automatically test, build, and deploy changes
2. Ensure code quality and security
3. Automate dependency updates
4. Support multi-environment deployments

## GitHub Actions Workflows

### Component Workflows

- **Backend CI/CD**: Runs tests, builds Docker image, and deploys backend
- **Web CI/CD**: Lints, builds, and deploys web frontend
- **Browser Extension CI/CD**: Builds and publishes the browser extension

### Integration Workflows

- **Integration CI/CD**: Runs E2E tests, security scans, builds all Docker images, and deploys
- **Dependency Updates**: Automatically updates dependencies weekly and opens PRs

## Relationship with Makefile

The Makefile provides local development commands that mirror the CI/CD processes:

| CI/CD Process | Makefile Target | GitHub Action Equivalent |
|---------------|-----------------|--------------------------|
| Backend Tests | `make backend-test` | Backend CI job |
| Web Lint/Build | `make web-lint web-build` | Web CI job |
| Extension Build | `make extension-build` | Extension CI job |
| Docker Build | `make docker-build` | docker-build-all job |
| Deployment | `make deploy` | deploy job |
| Dependency Updates | `make update` | dependency-updates workflow |

## Local Development vs CI/CD

While the Makefile targets are designed for local development, the CI/CD workflows run the same commands in a controlled environment with proper secrets and configuration.

### Key Differences

- **Environment Variables**: CI/CD uses GitHub Secrets for sensitive values
- **Deployments**: CI/CD automates remote deployment via SSH
- **Docker Registry**: CI/CD pushes images to Docker Hub
- **Notifications**: CI/CD sends Slack notifications after deployments
- **Security Scans**: CI/CD runs additional security scans

## Manual Workflows

Some workflows support manual triggering with custom parameters:

- **Integration workflow**: Can manually select deployment environment and enable/disable full test suite
- **Component workflows**: Can manually trigger builds for specific components

## Adding New CI/CD Components

When adding new components to the system:

1. Create corresponding Makefile targets for local testing/building
2. Add appropriate GitHub Actions workflow jobs
3. Update documentation

## Secrets Management

The CI/CD system requires various secrets to be configured in GitHub:

- Docker Hub credentials
- SSH deployment keys
- Extension publishing keys
- Notification webhooks

## Continuous Improvement

The CI/CD system is designed to evolve with the project:

- Add new test types as needed
- Incorporate additional security scanning
- Improve deployment strategies
- Add performance testing

## Getting Started

To develop locally with alignment to CI/CD:

1. Use the Makefile to run the same commands locally
2. Ensure your changes pass the same checks that CI will run
3. When ready, push changes and let the CI/CD system handle testing and deployment 