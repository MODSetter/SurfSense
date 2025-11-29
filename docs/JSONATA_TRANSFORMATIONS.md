# JSONata Transformations in SurfSense

## Overview

SurfSense uses [JSONata](https://jsonata.org/) for declarative data transformation from external APIs. This approach provides a maintainable, testable way to convert connector-specific JSON responses into SurfSense's standardized Document format.

## Why JSONata?

- **Declarative**: Define transformations as data, not code
- **Maintainable**: Templates are easier to read and update than Python code
- **Testable**: JSONata expressions can be tested independently
- **Consistent**: All connectors follow the same transformation pattern
- **Powerful**: Supports filtering, aggregation, string manipulation, and more

## Architecture

### Core Components

1. **JSONataTransformer** (`app/services/jsonata_transformer.py`)
   - Global singleton service for applying transformations
   - Methods: `transform()`, `transform_custom()`, `register_template()`

2. **Connector Templates** (`app/config/jsonata_templates.py`)
   - Pre-defined JSONata expressions for each connector type
   - Registered at application startup

3. **API Endpoints** (`app/routes/jsonata_routes.py`)
   - `/api/v1/jsonata/transform` - Test custom transformations
   - `/api/v1/jsonata/templates` - List registered templates
   - `/api/v1/jsonata/templates/{connector_type}` - Check template existence

## Document Format

All transformations produce this standardized structure:

```json
{
  "title": "Document title",
  "content": "Main document content/body",
  "document_type": "CONNECTOR_TYPE",
  "document_metadata": {
    "url": "https://...",
    "author": "username",
    "created_at": "2025-11-29T10:00:00Z",
    // ... connector-specific metadata
  }
}
```

## Adding New Connector Transformations

### Step 1: Define JSONata Template

Add your template to `app/config/jsonata_templates.py`:

```python
# Example: Asana Task Template
ASANA_TASK_TEMPLATE = """
{
    "title": name,
    "content": notes,
    "document_type": "ASANA_CONNECTOR",
    "document_metadata": {
        "task_id": gid,
        "project": $exists(projects[0]) ? projects[0].name : null,
        "assignee": $exists(assignee) ? assignee.name : null,
        "due_date": $exists(due_on) ? due_on : null,
        "completed": completed,
        "tags": $exists(tags) ? tags.name : []
    }
}
"""
```

### Step 2: Register Template

Add to `CONNECTOR_TEMPLATES` dictionary:

```python
CONNECTOR_TEMPLATES = {
    # ... existing templates
    "asana": ASANA_TASK_TEMPLATE,
}
```

### Step 3: Use in Connector

Apply transformation in your connector code:

```python
from app.services.jsonata_transformer import transformer

class AsanaConnector(BaseConnector):
    async def fetch_data(self):
        # Fetch from Asana API
        asana_response = await self._fetch_from_asana()

        # Transform using JSONata
        if transformer.has_template("asana"):
            standardized_data = transformer.transform("asana", asana_response)
        else:
            # Fallback to manual transformation
            standardized_data = self._manual_transform(asana_response)

        return standardized_data
```

### Step 4: Add Tests

Create tests in `tests/test_jsonata_transformer.py`:

```python
def test_asana_task_transformation(self):
    """Test Asana task transformation."""
    transformer = JSONataTransformer()
    transformer.register_template("asana", ASANA_TASK_TEMPLATE)

    asana_response = {
        "name": "Fix login bug",
        "notes": "Users cannot authenticate",
        "gid": "1234567890",
        "projects": [{"name": "Backend"}],
        "assignee": {"name": "John Doe"},
        "due_on": "2025-12-01",
        "completed": False,
        "tags": [{"name": "bug"}, {"name": "urgent"}]
    }

    result = transformer.transform("asana", asana_response)

    assert result["title"] == "Fix login bug"
    assert result["document_type"] == "ASANA_CONNECTOR"
    assert result["document_metadata"]["assignee"] == "John Doe"
```

## JSONata Syntax Reference

### Basic Field Access

```jsonata
title                  # Access 'title' field
user.name              # Nested field access
items[0]               # Array indexing
items.price            # Map over array
```

### String Manipulation

```jsonata
$substring(text, 0, 100)           # First 100 characters
$uppercase(name)                    # Convert to uppercase
$join(items, ", ")                  # Join array with delimiter
```

### Filtering and Predicates

```jsonata
issues[state='open']                # Filter array
items[price > 100]                  # Numeric comparison
labels.name                         # Extract field from array
```

### Aggregation Functions

```jsonata
$sum(items.price)                   # Sum values
$count(items)                       # Count items
$max(items.score)                   # Maximum value
$min(items.score)                   # Minimum value
```

### Conditional Logic

```jsonata
{
    "status": completed ? "done" : "pending",
    "priority": $exists(due_date) ? "urgent" : "normal"
}
```

### Object Construction

```jsonata
{
    "title": title,
    "metadata": {
        "author": user.login,
        "created": created_at
    }
}
```

## Example Templates

### GitHub Issue/PR

```jsonata
{
    "title": title,
    "content": body,
    "document_type": "GITHUB_CONNECTOR",
    "document_metadata": {
        "url": html_url,
        "author": user.login,
        "created_at": created_at,
        "updated_at": updated_at,
        "labels": labels.name,
        "state": state,
        "comments_count": comments,
        "repository": repository_url,
        "number": number,
        "is_pull_request": $exists(pull_request)
    }
}
```

### Slack Message

```jsonata
{
    "title": $substring(text, 0, 100),
    "content": text,
    "document_type": "SLACK_CONNECTOR",
    "document_metadata": {
        "channel": channel,
        "channel_name": channel_name,
        "user": user,
        "user_name": user_name,
        "timestamp": ts,
        "thread_ts": thread_ts,
        "reactions": reactions.{
            "name": name,
            "count": count,
            "users": users
        }
    }
}
```

### Jira Issue

```jsonata
{
    "title": fields.summary,
    "content": fields.description,
    "document_type": "JIRA_CONNECTOR",
    "document_metadata": {
        "key": key,
        "status": fields.status.name,
        "priority": fields.priority.name,
        "issue_type": fields.issuetype.name,
        "assignee": fields.assignee.displayName,
        "reporter": fields.reporter.displayName,
        "project": fields.project.name,
        "labels": fields.labels
    }
}
```

## Testing Transformations

### Using the API

Test custom JSONata expressions via the API:

```bash
curl -X POST http://localhost:8000/api/v1/jsonata/transform \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonata_expression": "{ \"title\": title, \"author\": user.name }",
    "data": {
      "title": "Test Document",
      "user": {"name": "John Doe"},
      "extra": "ignored"
    }
  }'
```

### Online Playground

Use [try.jsonata.org](https://try.jsonata.org/) to test expressions before adding them:

1. Paste sample API response in "Input" panel
2. Write JSONata expression in "Expression" panel
3. See transformed output in "Output" panel

### Unit Tests

All transformations should have corresponding unit tests:

```python
def test_my_connector_transformation(self):
    """Test my connector transformation."""
    transformer = JSONataTransformer()
    transformer.register_template("my_connector", MY_TEMPLATE)

    # Sample API response
    api_response = {...}

    # Transform
    result = transformer.transform("my_connector", api_response)

    # Assertions
    assert result["title"] == "Expected Title"
    assert result["document_type"] == "MY_CONNECTOR"
```

## Best Practices

### 1. Handle Missing Fields Gracefully

```jsonata
{
    "optional_field": $exists(optional) ? optional : null
}
```

### 2. Provide Fallback Values

```jsonata
{
    "title": title ? title : "Untitled Document"
}
```

### 3. Extract Rich Metadata

Include as much context as possible in `document_metadata`:

```jsonata
{
    "document_metadata": {
        "url": html_url,
        "author": user.login,
        "created_at": created_at,
        "tags": labels.name,
        "mentions": mentions.username
    }
}
```

### 4. Keep Templates Readable

Use multi-line strings and proper indentation:

```python
TEMPLATE = """
{
    "title": title,
    "content": body,
    "document_metadata": {
        "author": user.name,
        "created": created_at
    }
}
"""
```

### 5. Document Field Mappings

Add comments explaining non-obvious transformations:

```python
# GitHub's 'body' field maps to our 'content' field
# 'user.login' extracts the username from nested user object
GITHUB_TEMPLATE = """..."""
```

## Troubleshooting

### Invalid JSONata Syntax

**Error**: `Exception: JSONata transformation failed`

**Solution**: Test expression at [try.jsonata.org](https://try.jsonata.org/) first

### Missing Fields

**Error**: Transformation returns `null` for expected fields

**Solution**: Check API response structure, use `$exists()` for optional fields

### Type Mismatches

**Error**: Expected string, got array

**Solution**: Use `$join()` to convert arrays to strings:

```jsonata
"content": $join(paragraphs, "\n")
```

## Migration Strategy

### Gradual Migration

1. Add JSONata template for connector
2. Keep existing Python transformation as fallback
3. Test JSONata transformation in staging
4. Remove fallback code after validation

### Example Migration Pattern

```python
def transform_data(self, api_response):
    # New JSONata transformation
    if transformer.has_template("my_connector"):
        try:
            return transformer.transform("my_connector", api_response)
        except Exception as e:
            logger.warning(f"JSONata failed, using fallback: {e}")
            # Fall back to Python transformation
            return self._legacy_transform(api_response)

    # Legacy transformation
    return self._legacy_transform(api_response)
```

## Resources

- [JSONata Documentation](https://docs.jsonata.org/)
- [JSONata Online Playground](https://try.jsonata.org/)
- [JSONata Cheat Sheet](https://docs.jsonata.org/overview)
- [pyjsonata GitHub](https://github.com/qntfy/pyjsonata)

## Support

For questions or issues:
1. Check existing connector templates in `app/config/jsonata_templates.py`
2. Test expressions at [try.jsonata.org](https://try.jsonata.org/)
3. Review unit tests in `tests/test_jsonata_transformer.py`
4. Create GitHub issue if needed
