# SurfSense CI/CD Workflows

This directory contains GitHub Actions workflows for automating the building, testing, and deployment of SurfSense components.

## Workflows Overview

### Component-specific Workflows

- **`backend-ci.yml`**: Handles backend testing, building, and deployment
- **`web-ci.yml`**: Handles web frontend testing, building, and deployment
- **`extension-ci.yml`**: Handles browser extension building and publishing to extension stores

### Integration Workflows

- **`integration-ci.yml`**: Comprehensive workflow that runs end-to-end tests, security scans, builds all Docker images and deploys to the target environment
- **`dependency-updates.yml`**: Automated dependency updates for all components, running weekly and creating PRs with updates

## Secrets Required

To successfully run these workflows, you need to configure the following repository secrets:

### Docker Hub
- `DOCKER_HUB_USERNAME`: Docker Hub username
- `DOCKER_HUB_TOKEN`: Docker Hub access token

### Deployment
- `DEPLOY_HOST`: Hostname/IP of the deployment server
- `DEPLOY_USER`: SSH username for deployment
- `DEPLOY_SSH_KEY`: SSH private key for deployment

### Browser Extension Publishing
- `CHROME_EXTENSION_KEYS`: Keys for Chrome Web Store
- `FIREFOX_EXTENSION_KEYS`: Keys for Firefox Add-ons
- `EDGE_EXTENSION_KEYS`: Keys for Microsoft Edge Add-ons

### Notifications
- `SLACK_WEBHOOK_URL`: Webhook URL for Slack notifications

## Workflow Environments

The workflows use GitHub Environments to control deployment targets:

- **Production**: Used for main/master branch deployments
- **Staging**: Used for manual deployments via workflow dispatch

## Triggering Workflows

### Automated Triggers
- Component workflows trigger on changes to their respective directories
- Integration workflow triggers on pushes to main/master branch
- Dependency updates run weekly (Monday at midnight UTC)

### Manual Triggers
All workflows can be manually triggered via the "workflow_dispatch" event in GitHub Actions UI.

The Integration workflow includes additional options when triggered manually:
- Select deployment environment (staging/production)
- Choose whether to run full test suite

## Extending Workflows

When adding new components or changing the build process:

1. Update the relevant component workflow
2. Ensure the integration workflow includes the new component
3. Update secrets if new ones are required

For environment-specific configurations, use GitHub Environments to manage environment variables. 