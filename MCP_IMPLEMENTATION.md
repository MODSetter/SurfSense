# MCP (Model Context Protocol) Implementation

## Overview

MCP connectors allow users to add custom API endpoints as tools for the AI agent to use. This enables integration with any HTTP API without writing custom code.

## Architecture

### Backend Components

1. **Database Enum** (`app/db.py`)
   - Added `MCP_CONNECTOR` to `SearchSourceConnectorType` enum
   - Stores tool configurations in connector `config` JSONB field

2. **Tool Factory** (`app/agents/new_chat/tools/mcp_tool.py`)
   - `create_mcp_tool_instance()` - Creates LangChain tools from API configurations
   - `load_mcp_tools()` - Loads all active MCP tools from database
   - Dynamic Pydantic model generation from JSON schema
   - Support for multiple auth types: Bearer, API Key, Basic Auth, None

3. **Registry Integration** (`app/agents/new_chat/tools/registry.py`)
   - New `build_tools_async()` function that loads MCP tools
   - Automatically includes user's MCP tools when building agent tools

4. **API Schemas** (`app/schemas/search_source_connector.py`)
   - `MCPToolConfig` - Configuration for individual API tool
   - `MCPConnectorCreate` - Create new MCP connector with tools
   - `MCPConnectorUpdate` - Update MCP connector
   - `MCPConnectorRead` - Read MCP connector with tools

5. **API Routes** (`app/routes/search_source_connectors_routes.py`)
   - `POST /api/v1/connectors/mcp` - Create MCP connector
   - `GET /api/v1/connectors/mcp` - List MCP connectors
   - `GET /api/v1/connectors/mcp/{id}` - Get specific MCP connector
   - `PUT /api/v1/connectors/mcp/{id}` - Update MCP connector
   - `DELETE /api/v1/connectors/mcp/{id}` - Delete MCP connector

## Usage Example

### Creating an MCP Connector

```bash
POST /api/v1/connectors/mcp?search_space_id=1
Content-Type: application/json

{
  "name": "Weather API",
  "tools": [
    {
      "name": "get_weather",
      "description": "Get current weather for a location",
      "endpoint": "https://api.openweathermap.org/data/2.5/weather",
      "method": "GET",
      "auth_type": "api_key",
      "auth_config": {
        "api_key": "your_api_key_here",
        "api_key_header": "X-API-Key"
      },
      "parameters": {
        "type": "object",
        "properties": {
          "location": {
            "type": "string",
            "description": "City name"
          },
          "units": {
            "type": "string",
            "description": "Temperature units (metric/imperial)"
          }
        },
        "required": ["location"]
      }
    }
  ]
}
```

### Tool Configuration Schema

```typescript
{
  name: string;              // Tool name (must be unique)
  description: string;       // Tool description for the agent
  endpoint: string;          // API endpoint URL
  method: string;           // HTTP method: GET, POST, PUT, PATCH, DELETE
  auth_type: string;        // Auth type: none, bearer, api_key, basic
  auth_config: {
    // For bearer auth
    token?: string;
    
    // For API key auth
    api_key?: string;
    api_key_header?: string;  // Default: "X-API-Key"
    
    // For basic auth
    username?: string;
    password?: string;
  };
  parameters: {              // JSON Schema for parameters
    type: "object";
    properties: {
      [key: string]: {
        type: "string" | "number" | "integer" | "boolean" | "array" | "object";
        description: string;
      }
    };
    required?: string[];
  };
}
```

## Authentication Types

1. **None** - No authentication
   ```json
   {"auth_type": "none", "auth_config": {}}
   ```

2. **Bearer Token**
   ```json
   {
     "auth_type": "bearer",
     "auth_config": {
       "token": "your_bearer_token"
     }
   }
   ```

3. **API Key**
   ```json
   {
     "auth_type": "api_key",
     "auth_config": {
       "api_key": "your_api_key",
       "api_key_header": "X-API-Key"
     }
   }
   ```

4. **Basic Auth**
   ```json
   {
     "auth_type": "basic",
     "auth_config": {
       "username": "user",
       "password": "pass"
     }
   }
   ```

## Agent Integration

MCP tools are automatically loaded when building agent tools:

```python
from app.agents.new_chat.tools.registry import build_tools_async

# Build tools including MCP tools
tools = await build_tools_async(
    dependencies={
        "search_space_id": 123,
        "db_session": session,
        "connector_service": service,
    },
    include_mcp_tools=True  # Default is True
)
```

## Frontend Integration (To Be Implemented)

The frontend needs to add:

1. **MCP Connector Card** in connectors list
2. **MCP Connector Form** with:
   - Connector name input
   - Tool list editor (add/remove tools)
   - For each tool:
     - Name, description
     - Endpoint URL
     - HTTP method selector
     - Auth type selector
     - Auth config inputs (conditional on auth type)
     - Parameter schema editor (JSON schema or form-based)

3. **Tool Testing** - Ability to test API calls before saving

## Database Migration

```bash
# Migration: 1053d0947cc1_add_mcp_connector_type.py
# Adds MCP_CONNECTOR to SearchSourceConnectorType enum
alembic upgrade head
```

## Security Considerations

1. **Credentials Storage** - Auth tokens/keys should be encrypted in the database
2. **Rate Limiting** - Consider adding rate limits for MCP tool calls
3. **URL Validation** - Validate endpoint URLs to prevent SSRF attacks
4. **Timeouts** - All API calls have 30-second timeout
5. **Error Handling** - API errors are caught and returned to agent

## Future Enhancements

1. **Request/Response Transformers** - Allow users to transform API responses
2. **Retry Logic** - Configurable retry behavior for failed API calls
3. **Caching** - Cache API responses with TTL
4. **Webhooks** - Support for webhook-based tools
5. **OAuth 2.0** - Support for OAuth 2.0 authentication flow
6. **GraphQL** - Support for GraphQL queries
7. **Tool Templates** - Pre-built templates for popular APIs
