# SurfSense Backend Tests

Comprehensive test suite for the SurfSense backend application using pytest with async support.

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures and test configuration
├── test_secrets_loader.py           # Configuration and secrets management tests
├── test_two_fa_service.py           # Two-factor authentication service tests
├── test_search_spaces_routes.py     # Search spaces API endpoint tests
├── test_page_limit_service.py       # Page limit service tests
└── README.md                        # This file
```

## Running Tests

### Run All Tests

```bash
cd /home/user/SurfSense/surfsense_backend
pytest
```

### Run with Coverage Report

```bash
pytest --cov=app --cov-report=html
```

The coverage report will be generated in `htmlcov/index.html`.

### Run Specific Test Categories

```bash
# Run only unit tests
pytest -m unit

# Run only API tests
pytest -m api

# Run only integration tests
pytest -m integration

# Run only service tests
pytest -m services

# Run only auth-related tests
pytest -m auth

# Run only database tests
pytest -m db
```

### Run Specific Test Files

```bash
pytest tests/test_two_fa_service.py
pytest tests/test_search_spaces_routes.py
```

### Run Tests in Parallel

```bash
pytest -n auto
```

### Run Tests with Verbose Output

```bash
pytest -v
pytest -vv  # Extra verbose
```

### Skip Slow Tests

```bash
pytest -m "not slow"
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Unit tests (testing individual functions/methods)
- `@pytest.mark.integration` - Integration tests (testing multiple components together)
- `@pytest.mark.e2e` - End-to-end tests (testing complete workflows)
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.services` - Service layer tests
- `@pytest.mark.models` - Database model tests
- `@pytest.mark.auth` - Authentication and authorization tests
- `@pytest.mark.db` - Tests requiring database access
- `@pytest.mark.slow` - Tests that take longer to run

## Test Fixtures

Common fixtures are defined in `conftest.py`:

### Database Fixtures

- `async_engine` - Async SQLAlchemy engine with in-memory SQLite
- `async_session` - Async database session
- `test_client` - Async HTTP client for API testing

### User Fixtures

- `test_user` - Regular user account
- `test_superuser` - Admin/superuser account
- `test_user_with_2fa` - User with 2FA enabled
- `auth_token` - JWT authentication token
- `auth_headers` - Authorization headers for requests

### Model Fixtures

- `test_search_space` - Test search space
- `test_document` - Test document
- `test_chat` - Test chat conversation

### Mock Fixtures

- `mock_llm_service` - Mocked LLM service
- `mock_embedding_service` - Mocked embedding service
- `mock_connector_service` - Mocked connector service
- `mock_celery_task` - Mocked Celery background task

### Data Generation

- `faker_instance` - Faker instance for generating test data
- `sample_user_data` - Sample user registration data
- `sample_search_space_data` - Sample search space data
- `sample_document_data` - Sample document data
- `sample_pdf_file` - Minimal valid PDF file bytes
- `sample_text_file` - Sample text file bytes

## Writing New Tests

### Basic Test Structure

```python
import pytest
from httpx import AsyncClient

@pytest.mark.unit
@pytest.mark.asyncio
async def test_example(test_client: AsyncClient):
    """Test description."""
    response = await test_client.get("/endpoint")
    assert response.status_code == 200
```

### Testing Async Functions

```python
@pytest.mark.asyncio
async def test_async_function(async_session):
    """Test async database function."""
    result = await some_async_function(async_session)
    assert result is not None
```

### Testing API Endpoints

```python
@pytest.mark.api
@pytest.mark.asyncio
async def test_api_endpoint(test_client, auth_headers):
    """Test API endpoint with authentication."""
    response = await test_client.post(
        "/api/endpoint",
        json={"data": "value"},
        headers=auth_headers,
    )
    assert response.status_code == 200
```

### Testing Services

```python
@pytest.mark.services
@pytest.mark.asyncio
async def test_service(async_session):
    """Test service layer."""
    service = MyService(session=async_session)
    result = await service.do_something()
    assert result == expected_value
```

## Test Coverage Goals

Target test coverage: **70%+**

Priority areas for testing:
1. **API Routes** - All CRUD endpoints
2. **Authentication** - Login, registration, 2FA, OAuth
3. **Services** - Business logic layer
4. **Database Models** - Model relationships and constraints
5. **Validators** - Input validation logic
6. **Security** - Authorization, ownership checks, rate limiting

## CI/CD Integration

Tests are automatically run on:
- Pull requests
- Push to main branch
- Nightly builds

See `.github/workflows/` for CI configuration.

## Troubleshooting

### Database Issues

If you encounter database-related errors:

```bash
# Reset test database
pytest --create-db
```

### Import Errors

Ensure the application is installed in development mode:

```bash
pip install -e .
```

### Async Warnings

If you see warnings about unclosed async resources, ensure you're using `@pytest.mark.asyncio` and proper async fixtures.

## Best Practices

1. **Test Isolation** - Each test should be independent and not rely on other tests
2. **Clear Names** - Use descriptive test names that explain what is being tested
3. **Arrange-Act-Assert** - Structure tests with clear setup, execution, and verification
4. **Mock External Services** - Don't make real API calls in tests
5. **Test Edge Cases** - Include tests for error conditions and boundary cases
6. **Keep Tests Fast** - Mark slow tests with `@pytest.mark.slow`

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [httpx Testing Documentation](https://www.python-httpx.org/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
