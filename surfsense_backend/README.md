# SurfSense Backend

FastAPI-based backend service for SurfSense.

## Quick Start

### Using Docker (Recommended)

```bash
# From the project root
docker compose up -d
```

This starts all services:
- **Backend API** at `http://localhost:8000`
- **PostgreSQL** with pgvector at `localhost:5432`
- **Redis** at `localhost:6379`
- **Celery Worker** for background tasks
- **Flower** (Celery monitor) at `http://localhost:5555`

### Manual Setup

```bash
cd surfsense_backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install dependencies
pip install uv
uv pip install -e .

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start the server
uvicorn main:app --reload
```

## Testing

We use **pytest** with **pytest-asyncio** for testing. Tests run inside Docker to ensure all dependencies (PostgreSQL, Redis) are available.

### Running Tests

```bash
# From the project root directory

# 1. Start dependencies
docker compose up -d db redis

# 2. Build the backend image (pytest is included)
docker compose build backend

# 3. Run all tests
docker compose run --rm -e TESTING=true backend pytest tests/ -v --tb=short

# 4. Run with coverage report
docker compose run --rm -e TESTING=true backend pytest tests/ -v --tb=short --cov=app --cov-report=html

# 5. Run specific test file
docker compose run --rm -e TESTING=true backend pytest tests/test_celery_tasks.py -v

# 6. Run tests matching a pattern
docker compose run --rm -e TESTING=true backend pytest tests/ -v -k "test_slack"

# 7. Stop services when done
docker compose down -v
```

### Test Structure

```
tests/
├── conftest.py                          # Shared fixtures
├── test_celery_tasks.py                 # Celery task tests
├── test_celery_tasks_comprehensive.py   # Comprehensive Celery tests
├── test_connector_indexers_comprehensive.py  # Connector indexer tests
├── test_external_connectors_comprehensive.py # External connector tests
├── test_document_processors_comprehensive.py # Document processor tests
├── test_connector_service.py            # Connector service tests
├── test_llm_service.py                  # LLM service tests
├── test_retrievers.py                   # Retriever tests
├── test_routes_*.py                     # API route tests
└── ...
```

### Writing Tests

- Use `pytest.mark.asyncio` for async tests
- Use fixtures from `conftest.py` for common setup
- Mock external services (LLMs, APIs) appropriately
- Follow the existing test patterns for consistency

Example async test:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_example():
    with patch("app.services.some_service.external_api") as mock_api:
        mock_api.return_value = {"result": "success"}
        # Your test code here
        assert result == expected
```

### CI/CD

Tests run automatically on GitHub Actions for:
- Pull requests to `main` and `dev` branches
- Pushes to `main` and `dev` branches

The CI uses Docker Compose to run tests with the same dependencies as local development.

## Project Structure

```
surfsense_backend/
├── app/
│   ├── agents/         # AI agent implementations
│   ├── config/         # Configuration management
│   ├── connectors/     # External service connectors
│   ├── prompts/        # LLM prompts
│   ├── retriver/       # Search and retrieval logic
│   ├── routes/         # API endpoints
│   ├── schemas/        # Pydantic models
│   ├── services/       # Business logic services
│   ├── tasks/          # Celery background tasks
│   └── utils/          # Utility functions
├── alembic/            # Database migrations
├── tests/              # Test suite
├── main.py             # Application entry point
├── celery_worker.py    # Celery worker entry point
└── pyproject.toml      # Project dependencies
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `CELERY_BROKER_URL` | Redis URL for Celery broker |
| `CELERY_RESULT_BACKEND` | Redis URL for Celery results |
| `SECRET_KEY` | JWT secret key |
| `TESTING` | Set to `true` for test mode |

See `.env.example` for all available options.

## API Documentation

When running locally, access the API docs at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
