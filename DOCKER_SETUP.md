# Docker Setup for SurfSense

This document explains how to run the SurfSense project using Docker Compose.

## Prerequisites

- Docker and Docker Compose installed on your machine
- Git (to clone the repository)

## Setup

1. Make sure you have all the necessary environment variables set up:
   - Copy `surfsense_backend/.env.example` to `surfsense_backend/.env` and fill in the required values
   - Copy `surfsense_frontend/.env.example` to `surfsense_frontend/.env.local` and fill in the required values

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
- Port: 5432
- Username: postgres
- Password: postgres
- Database: surfsense

You can connect to it using any PostgreSQL client.

## Troubleshooting

- If you encounter permission errors, you may need to run the docker commands with `sudo`.
- If ports are already in use, modify the port mappings in the `docker-compose.yml` file.
- For backend dependency issues, you may need to modify the `Dockerfile` in the backend directory.
- For frontend dependency issues, you may need to modify the `Dockerfile` in the frontend directory. 
