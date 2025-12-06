# SurfSense Backend

Python/FastAPI backend service for SurfSense.

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL with PGVector extension
- Redis (for Celery task queue)
- Docker & Docker Compose (recommended)

### Development Setup

1. **Clone and navigate to backend**
   ```bash
   cd surfsense_backend
   ```

2. **Install dependencies with UV**
   ```bash
   uv sync
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run database migrations**
   ```bash
   uv run alembic upgrade head
   ```

5. **Start the development server**
   ```bash
   uv run uvicorn app.app:app --reload
   ```

## Testing

We use pytest for testing with Docker Compose for dependencies.

### Running Tests

```bash
# Start dependencies
docker compose up -d db redis

# Run all tests
docker compose run --rm -e TESTING=true backend pytest tests/ -v --tb=short

# Run with coverage
docker compose run --rm -e TESTING=true backend pytest tests/ -v --tb=short --cov=app --cov-report=html

# Run specific test file
docker compose run --rm -e TESTING=true backend pytest tests/test_celery_tasks.py -v

# Run tests matching a pattern
docker compose run --rm -e TESTING=true backend pytest tests/ -v -k "test_slack"

# Stop services
docker compose down -v
```

### Test Categories

Tests are organized by markers:
- `@pytest.mark.unit` - Fast, isolated unit tests
- `@pytest.mark.integration` - Tests requiring external services
- `@pytest.mark.slow` - Slow running tests

### Running Locally (without Docker)

```bash
# Ensure PostgreSQL and Redis are running locally
export TESTING=true
uv run pytest tests/ -v --tb=short
```

## Project Structure

```
surfsense_backend/
├── alembic/              # Database migrations
│   ├── versions/         # Migration files
│   └── env.py           # Alembic configuration
├── app/
│   ├── __init__.py
│   ├── app.py           # FastAPI application
│   ├── celery_app.py    # Celery configuration
│   ├── db.py            # Database models
│   ├── users.py         # User authentication
│   ├── agents/          # LLM agents (researcher, podcaster)
│   ├── config/          # Configuration management
│   ├── connectors/      # External service connectors
│   ├── prompts/         # LLM prompts
│   ├── retriever/       # Search and retrieval logic
│   ├── routes/          # API endpoints
│   ├── schemas/         # Pydantic models
│   ├── services/        # Business logic services
│   ├── tasks/           # Celery tasks
│   └── utils/           # Utility functions
├── tests/               # Test suite
│   ├── conftest.py     # Pytest fixtures
│   ├── test_*.py       # Test modules
│   └── __init__.py
├── Dockerfile           # Container configuration
├── pyproject.toml       # Project dependencies
├── pytest.ini          # Pytest configuration
└── alembic.ini         # Alembic configuration
```

## API Documentation

When running the development server, API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `CELERY_BROKER_URL` | Redis URL for Celery | Required |
| `SECRET_KEY` | Application secret key | Required |
| `TESTING` | Enable test mode | `false` |

See `.env.example` for full configuration options.

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines.
