# Docker Setup for SurfSense

This document explains how to run the SurfSense project using Docker Compose.

## Prerequisites

- Docker and Docker Compose installed on your machine
- Git (to clone the repository)

## Environment Variables Configuration

SurfSense Docker setup supports configuration through environment variables. You can set these variables in two ways:

1. Create a `.env` file in the project root directory (copy from `.env.example`)
2. Set environment variables directly in your shell before running Docker Compose

The following environment variables are available:

```
# Frontend Configuration
FRONTEND_PORT=3000
NEXT_PUBLIC_API_URL=http://backend:8000

# Backend Configuration
BACKEND_PORT=8000

# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=surfsense
POSTGRES_PORT=5432

# pgAdmin Configuration
PGADMIN_PORT=5050
PGADMIN_DEFAULT_EMAIL=admin@surfsense.com
PGADMIN_DEFAULT_PASSWORD=surfsense
```

## Setup

1. Make sure you have all the necessary environment variables set up:
   - Copy `surfsense_backend/.env.example` to `surfsense_backend/.env` and fill in the required values
   - Copy `surfsense_web/.env.example` to `surfsense_web/.env` and fill in the required values
   - Optionally: Copy `.env.example` to `.env` in the project root to customize Docker settings

2. Build and start the containers:
   ```bash
   docker-compose up --build
   ```

3. To run in detached mode (in the background):
   ```bash
   docker-compose up -d
   ```

4. Access the applications:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - pgAdmin: http://localhost:5050

## Useful Commands

- Stop the containers:
  ```bash
  docker-compose down
  ```

- View logs:
  ```bash
  # All services
  docker-compose logs -f
  
  # Specific service
  docker-compose logs -f backend
  docker-compose logs -f frontend
  docker-compose logs -f db
  docker-compose logs -f pgadmin
  ```

- Restart a specific service:
  ```bash
  docker-compose restart backend
  ```

- Execute commands in a running container:
  ```bash
  # Backend
  docker-compose exec backend python -m pytest
  
  # Frontend
  docker-compose exec frontend pnpm lint
  ```

## Database

The PostgreSQL database with pgvector extensions is available at:
- Host: localhost
- Port: 5432 (configurable via POSTGRES_PORT)
- Username: postgres (configurable via POSTGRES_USER)
- Password: postgres (configurable via POSTGRES_PASSWORD)
- Database: surfsense (configurable via POSTGRES_DB)

You can connect to it using any PostgreSQL client or the included pgAdmin.

## pgAdmin

pgAdmin is a web-based administration tool for PostgreSQL. It is included in the Docker setup for easier database management.

- URL: http://localhost:5050 (configurable via PGADMIN_PORT)
- Default Email: admin@surfsense.com (configurable via PGADMIN_DEFAULT_EMAIL)
- Default Password: surfsense (configurable via PGADMIN_DEFAULT_PASSWORD)

### Connecting to the Database in pgAdmin

1. Log in to pgAdmin using the credentials above
2. Right-click on "Servers" in the left sidebar and select "Create" > "Server"
3. In the "General" tab, give your connection a name (e.g., "SurfSense DB")
4. In the "Connection" tab, enter the following:
   - Host: db
   - Port: 5432
   - Maintenance database: surfsense
   - Username: postgres 
   - Password: postgres
5. Click "Save" to establish the connection

## Troubleshooting

- If you encounter permission errors, you may need to run the docker commands with `sudo`.
- If ports are already in use, modify the port mappings in the `.env` file or directly in the `docker-compose.yml` file.
- For backend dependency issues, you may need to modify the `Dockerfile` in the backend directory.
- For frontend dependency issues, you may need to modify the `Dockerfile` in the frontend directory.
- If pgAdmin doesn't connect to the database, ensure you're using `db` as the hostname, not `localhost`, as that's the Docker network name. 
