# MCP Frontend Implementation Guide

## ✅ Completed Frontend Implementation

All frontend code for MCP (Model Context Protocol) connectors has been implemented. Here's what was added:

### 1. Type Definitions

**File: `contracts/types/mcp.types.ts`** (NEW)
- `MCPToolConfig` - Type for individual tool configuration
- `MCPConnectorCreate/Update/Read` - CRUD types for MCP connectors
- Full Zod schemas for validation

**Updated Files:**
- `contracts/types/connector.types.ts` - Added `MCP_CONNECTOR` to enum
- `contracts/enums/connector.ts` - Added `MCP_CONNECTOR` to `EnumConnectorName`
- `contracts/enums/connectorIcons.tsx` - Added Webhook icon for MCP connectors

### 2. UI Component

**File: `components/assistant-ui/connector-popup/connector-configs/components/mcp-config.tsx`** (NEW)

Features:
- ✅ Connector name input
- ✅ Multiple tools support (add/remove tools)
- ✅ Tool configuration per tool:
  - Name (snake_case identifier)
  - Description (for AI agent)
  - API endpoint URL
  - HTTP method selector (GET/POST/PUT/PATCH/DELETE)
  - Authentication type selector (None/Bearer/API Key/Basic Auth)
  - Dynamic auth config inputs based on type
  - JSON Schema editor for parameters
- ✅ Responsive design
- ✅ Form validation

**Updated: `components/assistant-ui/connector-popup/connector-configs/index.tsx`**
- Registered MCP config component in factory

### 3. API Client

**Updated: `lib/apis/connectors-api.service.ts`**

Added methods:
- `getMCPConnectors(request)` - List all MCP connectors for a search space
- `getMCPConnector(id)` - Get single MCP connector
- `createMCPConnector(request)` - Create new MCP connector
- `updateMCPConnector(request)` - Update existing MCP connector
- `deleteMCPConnector(id)` - Delete MCP connector

All methods are fully typed with TypeScript generics.

## Usage Example

### Creating an MCP Connector via UI

1. Navigate to Connectors page
2. Click "Add Connector"
3. Select "MCP Connector" from the list
4. Fill in connector details:
   - Name: "Weather & News APIs"
   - Add Tool 1:
     - Name: `get_weather`
     - Description: "Get current weather for a location"
     - Endpoint: `https://api.openweathermap.org/data/2.5/weather`
     - Method: `GET`
     - Auth Type: `API Key`
     - API Key: `<your_key>`
     - Header Name: `X-API-Key`
     - Parameters:
       ```json
       {
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
       ```
   - Click "Add Tool" for additional APIs
5. Click "Save"

### Using MCP Tools in Chat

Once created, MCP tools are automatically available to the AI agent:

```
User: "What's the weather in San Francisco?"

Agent: Let me check the weather for you.
[Calls get_weather tool with location="San Francisco"]

Agent: The current weather in San Francisco is 62°F (17°C) with partly cloudy skies.
```

## Component Architecture

```
MCPConfig Component
├── Connector Name Input
└── Tools Array
    ├── Tool 1
    │   ├── Basic Info (name, description)
    │   ├── API Config (endpoint, method)
    │   ├── Authentication
    │   │   ├── None (no fields)
    │   │   ├── Bearer Token (token field)
    │   │   ├── API Key (key + header name)
    │   │   └── Basic Auth (username + password)
    │   └── Parameters (JSON Schema editor)
    ├── Tool 2
    └── [Add Tool Button]
```

## API Integration Flow

```
1. User fills form in MCPConfig component
   ↓
2. onConfigChange callback updates parent state
   ↓
3. Parent saves connector via createMCPConnector()
   ↓
4. API POST /api/v1/connectors/mcp
   ↓
5. Backend creates connector with tools in metadata
   ↓
6. Agent loads tools via load_mcp_tools() on next chat
```

## Authentication Support

### None
```json
{
  "auth_type": "none",
  "auth_config": {}
}
```

### Bearer Token
```json
{
  "auth_type": "bearer",
  "auth_config": {
    "token": "your_bearer_token"
  }
}
```

### API Key
```json
{
  "auth_type": "api_key",
  "auth_config": {
    "api_key": "your_api_key",
    "api_key_header": "X-API-Key"
  }
}
```

### Basic Auth
```json
{
  "auth_type": "basic",
  "auth_config": {
    "username": "user",
    "password": "pass"
  }
}
```

## Parameter Schema Examples

### Simple String Parameter
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search query"
    }
  },
  "required": ["query"]
}
```

### Multiple Parameters with Types
```json
{
  "type": "object",
  "properties": {
    "city": {
      "type": "string",
      "description": "City name"
    },
    "days": {
      "type": "integer",
      "description": "Number of forecast days"
    },
    "include_hourly": {
      "type": "boolean",
      "description": "Include hourly forecast"
    }
  },
  "required": ["city"]
}
```

### Nested Object
```json
{
  "type": "object",
  "properties": {
    "location": {
      "type": "object",
      "properties": {
        "lat": { "type": "number", "description": "Latitude" },
        "lon": { "type": "number", "description": "Longitude" }
      },
      "required": ["lat", "lon"]
    }
  },
  "required": ["location"]
}
```

## Files Modified

### New Files:
1. ✅ `contracts/types/mcp.types.ts`
2. ✅ `components/assistant-ui/connector-popup/connector-configs/components/mcp-config.tsx`

### Updated Files:
1. ✅ `contracts/types/connector.types.ts`
2. ✅ `contracts/enums/connector.ts`
3. ✅ `contracts/enums/connectorIcons.tsx`
4. ✅ `components/assistant-ui/connector-popup/connector-configs/index.tsx`
5. ✅ `lib/apis/connectors-api.service.ts`

## Testing Checklist

- [ ] Create MCP connector with single tool
- [ ] Create MCP connector with multiple tools
- [ ] Test all auth types (None, Bearer, API Key, Basic)
- [ ] Edit existing MCP connector
- [ ] Delete MCP connector
- [ ] Verify tools appear in chat agent
- [ ] Test API calls from agent to MCP tools
- [ ] Validate JSON schema parsing
- [ ] Test form validation
- [ ] Test responsive design on mobile

## Next Steps (Optional Enhancements)

1. **Tool Testing** - Add "Test Tool" button to make API call and show response
2. **Parameter Builder** - Visual form builder instead of JSON editor
3. **Tool Templates** - Pre-built templates for popular APIs (Weather, News, etc.)
4. **Import/Export** - Export connector config as JSON, import from file
5. **Response Transformers** - Allow JS functions to transform API responses
6. **Rate Limiting UI** - Show rate limits per tool
7. **Error Logs** - Display failed API calls in connector details
8. **OAuth 2.0** - Support for OAuth flow for APIs

## Need Help?

- Backend API docs: See `MCP_IMPLEMENTATION.md` in repo root
- Component props: Check `ConnectorConfigProps` interface
- Type definitions: See `contracts/types/mcp.types.ts`
- API client: See `lib/apis/connectors-api.service.ts`
