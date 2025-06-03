# SurfSense Deployment Guide

This guide explains the different deployment options available for SurfSense using Docker Compose.

## Deployment Options

SurfSense uses a flexible Docker Compose configuration that allows you to easily switch between deployment modes without manually editing files. Our approach uses Docker's built-in override functionality with two configuration files:

1. **docker-compose.yml**: Contains essential core services (database and pgAdmin)
2. **docker-compose.override.yml**: Contains application services (frontend and backend)

This structure provides several advantages:
- No need to comment/uncomment services manually
- Clear separation between core infrastructure and application services
- Easy switching between development and production environments

## Deployment Modes

### Full Stack Mode (Development)

This mode runs everything: frontend, backend, database, and pgAdmin. It's ideal for development environments where you need the complete application stack.

```bash
# Both files are automatically used (docker-compose.yml + docker-compose.override.yml)
docker compose up -d
```

### Core Services Mode (Production)

This mode runs only the database and pgAdmin services. It's suitable for production environments where you might want to deploy the frontend and backend separately or need to run database migrations.

```bash
# Explicitly use only the main file
docker compose -f docker-compose.yml up -d
```

## Custom Deployment Options

### Running Specific Services

You can specify which services to start by naming them:

```bash
# Start only database
docker compose up -d db

# Start database and pgAdmin
docker compose up -d db pgadmin

# Start only backend (requires db to be running)
docker compose up -d backend
```

### Using Custom Override Files

You can create and use custom override files for different environments:

```bash
# Create a staging configuration
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d
```

## Environment Variables

The deployment can be customized using environment variables:

```bash
# Change default ports
FRONTEND_PORT=4000 BACKEND_PORT=9000 docker compose up -d

# Or use a .env file
# Create or modify .env file with your desired values
docker compose up -d
```

## Common Deployment Workflows

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/MODSetter/SurfSense.git
cd SurfSense

# Copy example env files
cp .env.example .env
cp surfsense_backend/.env.example surfsense_backend/.env
cp surfsense_web/.env.example surfsense_web/.env

# Edit the .env files with your configuration

# Start full stack for development
docker compose up -d
```

### Database-Only Mode (for migrations or maintenance)

```bash
# Start just the database
docker compose -f docker-compose.yml up -d db

# Run migrations or maintenance tasks
docker compose exec db psql -U postgres -d surfsense
```

### Scaling in Production

For production deployments, you might want to:

1. Run core services with Docker Compose
2. Deploy frontend/backend with specialized services like Vercel, Netlify, or dedicated application servers

This separation allows for better scaling and resource utilization in production environments.

## Troubleshooting

If you encounter issues with the deployment:

- Check container logs: `docker compose logs -f [service_name]`
- Ensure all required environment variables are set
- Verify network connectivity between containers
- Check that required ports are available and not blocked by firewalls

For more detailed setup instructions, refer to [DOCKER_SETUP.md](DOCKER_SETUP.md). 