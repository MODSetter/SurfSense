# Trello Connector Tests

This document provides a comprehensive overview of the test suite for the Trello connector implementation.

## Test Structure

### Backend Tests

#### 1. Unit Tests (`test_trello_connector.py`)
- **Purpose**: Tests the core `TrelloConnector` class functionality
- **Coverage**: 
  - Initialization with valid/invalid credentials
  - API method calls (`get_user_boards`, `get_board_data`, `get_card_details`)
  - Error handling for various failure scenarios
  - Edge cases (empty responses, malformed data, timeouts)

#### 2. Comprehensive Tests (`test_trello_connector_comprehensive.py`)
- **Purpose**: Extended test coverage for all Trello connector components
- **Coverage**:
  - `TrelloConnector` class (enhanced)
  - `TrelloIndexer` functionality
  - API routes (`list_trello_boards`)
  - Database integration
  - Pydantic models (`TrelloCredentialsRequest`)
  - Indexing helper functions

#### 3. Integration Tests (`test_trello_integration.py`)
- **Purpose**: End-to-end testing of the complete Trello connector flow
- **Coverage**:
  - API endpoint integration
  - Database operations
  - Complete indexing workflow
  - Error scenarios and edge cases

#### 4. Test Configuration (`conftest.py`)
- **Purpose**: Shared fixtures and test configuration
- **Fixtures**:
  - Mock database sessions
  - Sample Trello data (boards, cards, comments)
  - Mock connectors and users
  - Error scenarios

### Frontend Tests

#### 1. Component Tests (`EditTrelloConnectorConfig.test.tsx`)
- **Purpose**: Tests the Trello connector configuration component
- **Coverage**:
  - Form validation
  - API integration
  - Board selection functionality
  - Error handling
  - User interactions

#### 2. Page Tests (`trello-connector.test.tsx`)
- **Purpose**: Tests the Trello connector creation page
- **Coverage**:
  - Form submission
  - Board fetching and selection
  - Connector creation flow
  - Navigation and routing
  - Loading states

## Test Categories

### 1. Unit Tests
- **TrelloConnector Class**: All methods and error handling
- **API Integration**: Mock HTTP requests and responses
- **Data Validation**: Input validation and error cases

### 2. Integration Tests
- **Database Operations**: Document creation and storage
- **API Endpoints**: Complete request/response cycles
- **Background Tasks**: Indexing workflow
- **Error Propagation**: End-to-end error handling

### 3. Frontend Tests
- **Component Behavior**: User interactions and state management
- **API Integration**: Mock fetch calls and responses
- **Form Validation**: Input validation and error display
- **Navigation**: Routing and page transitions

## Running Tests

### Backend Tests
```bash
# Run all Trello tests
python run_trello_tests.py

# Run specific test file
pytest tests/connectors/test_trello_connector.py -v

# Run specific test
python run_trello_tests.py test_initialization_success

# Run with coverage
pytest tests/connectors/ --cov=app.connectors.trello_connector --cov-report=html
```

### Frontend Tests
```bash
# Run all frontend tests
npm test

# Run specific test file
npm test EditTrelloConnectorConfig.test.tsx

# Run with coverage
npm test -- --coverage
```

## Test Data

### Sample Trello Boards
```json
[
  {"id": "board1", "name": "Project Board"},
  {"id": "board2", "name": "Personal Tasks"},
  {"id": "board3", "name": "Team Collaboration"}
]
```

### Sample Trello Cards
```json
[
  {
    "id": "card1",
    "name": "Implement user authentication",
    "desc": "Add login and registration functionality",
    "url": "https://trello.com/c/card1",
    "due": "2023-12-31T23:59:59.000Z",
    "labels": [{"name": "High Priority", "color": "red"}]
  }
]
```

### Sample Card Details
```json
{
  "id": "card1",
  "name": "Implement user authentication",
  "desc": "Add login and registration functionality with JWT tokens",
  "url": "https://trello.com/c/card1",
  "comments": [
    "This is a high priority task",
    "Make sure to include password reset functionality"
  ]
}
```

## Error Scenarios Tested

### API Errors
- Invalid credentials
- Network timeouts
- Connection errors
- HTTP errors (401, 403, 404, 500)
- Rate limiting
- Malformed responses

### Database Errors
- Connection failures
- Transaction rollbacks
- Constraint violations
- Missing records

### Frontend Errors
- Form validation failures
- API call failures
- Network errors
- Component state errors

## Mock Strategy

### Backend Mocks
- `requests.get`: Mock Trello API calls
- `AsyncSession`: Mock database operations
- `TrelloConnector`: Mock connector instances
- `current_active_user`: Mock authentication

### Frontend Mocks
- `fetch`: Mock API calls
- `toast`: Mock notifications
- `useRouter`: Mock Next.js routing
- `useSearchSourceConnectors`: Mock custom hooks

## Test Coverage Goals

- **Unit Tests**: 95%+ coverage for core classes
- **Integration Tests**: 90%+ coverage for API endpoints
- **Frontend Tests**: 90%+ coverage for components
- **Error Handling**: 100% coverage for error scenarios

## Continuous Integration

### Backend CI
- Run tests on Python 3.8, 3.9, 3.10, 3.11
- Check code coverage
- Run linting (flake8, black, isort)
- Run type checking (mypy)

### Frontend CI
- Run tests on Node.js 16, 18, 20
- Check code coverage
- Run linting (ESLint, Prettier)
- Run type checking (TypeScript)

## Performance Testing

### Backend Performance
- API response times
- Database query performance
- Memory usage during indexing
- Concurrent request handling

### Frontend Performance
- Component render times
- Bundle size impact
- Memory usage
- User interaction responsiveness

## Security Testing

### Backend Security
- Input validation
- SQL injection prevention
- Authentication and authorization
- API key handling

### Frontend Security
- XSS prevention
- CSRF protection
- Input sanitization
- Secure API communication

## Maintenance

### Test Maintenance
- Regular updates for API changes
- Dependency updates
- Test data refresh
- Performance optimization

### Documentation Updates
- Test case documentation
- API documentation
- Error handling documentation
- User guide updates

## Troubleshooting

### Common Issues
1. **Import Errors**: Ensure all dependencies are installed
2. **Mock Failures**: Check mock setup and return values
3. **Database Errors**: Verify test database configuration
4. **API Errors**: Check mock response format

### Debug Commands
```bash
# Debug specific test
pytest tests/connectors/test_trello_connector.py::TestTrelloConnector::test_initialization_success -v -s

# Run with debug output
pytest tests/connectors/ -v -s --log-cli-level=DEBUG

# Check test discovery
pytest --collect-only tests/connectors/
```

## Future Enhancements

### Planned Improvements
- Performance benchmarking
- Load testing
- Security testing automation
- Visual regression testing
- Accessibility testing

### Test Automation
- Automated test generation
- Test data management
- Continuous testing
- Test result reporting
