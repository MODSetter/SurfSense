# SurfSense CI/CD Workflows

This directory contains GitHub Actions workflows for automating the building and testing of SurfSense components.

## Workflows Overview

### Component-specific Workflows

- **`backend-ci.yml`**: Handles backend testing and linting
- **`web-ci.yml`**: Handles web frontend linting and building
- **`extension-ci.yml`**: Handles browser extension building and packaging
- **`dependency-updates.yml`**: Automated dependency updates for all components, running weekly

### Integration Workflows

- **`integration-ci.yml`**: Runs end-to-end tests and security scans for the codebase

## Workflow Functionality

These workflows have been simplified to focus on core development tasks:

- Code quality (linting)
- Test execution
- Extension and web app building
- Security scanning
- Dependency updates

## Triggering Workflows

### Automated Triggers
- Component workflows trigger on changes to their respective directories
- Integration workflow triggers on pushes to main/master branch
- Dependency updates run weekly (Monday at midnight UTC)

### Manual Triggers
All workflows can be manually triggered via the "workflow_dispatch" event in GitHub Actions UI.

The Integration workflow includes additional options when triggered manually:
- Choose whether to run full test suite

## Extending Workflows

When adding new components or changing the build process:

1. Update the relevant component workflow
2. Ensure the integration workflow includes the new component
3. Update secrets if new ones are required

For environment-specific configurations, use GitHub Environments to manage environment variables. 