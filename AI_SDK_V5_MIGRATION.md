# AI SDK v5 Migration Plan

## Overview

This document outlines the migration plan for upgrading from Vercel AI SDK v4 to v5 in SurfSense.

## Current State

- **Current Version**: `ai@^4.3.19`
- **Target Version**: `ai@^5.0.95`
- **Affected Files**: 7+ files in `surfsense_web/`

## Breaking Changes Summary

### 1. useChat Hook Changes

#### `initialMessages` → `messages`
```typescript
// OLD (v4)
const handler = useChat({
  initialMessages: [],
  // ...
});

// NEW (v5)
const handler = useChat({
  messages: [],
  // ...
});
```

**Affected File**: `surfsense_web/app/dashboard/[search_space_id]/researcher/[[...chat_id]]/page.tsx:106`

#### `body` Parameter Behavior
In v5, the `body` value is captured only at first render and remains static. Dynamic values must be passed via `chatRequestOptions`.

```typescript
// OLD (v4) - Dynamic body values
const handler = useChat({
  body: {
    data: {
      selected_connectors: connectorTypes,  // This won't update!
      document_ids: documentIds,
    },
  },
});

// NEW (v5) - Use chatRequestOptions for dynamic values
handler.append(message, {
  body: {
    data: {
      selected_connectors: connectorTypes,
      document_ids: documentIds,
    },
  },
});
```

#### `maxSteps` Removed
If using `maxSteps`, replace with server-side `stopWhen` conditions.

### 2. Message Format Changes

Messages now use a `parts` array instead of a `content` string.

```typescript
// OLD (v4)
interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
}

// NEW (v5)
interface UIMessage {
  id: string;
  role: "user" | "assistant" | "system";
  parts: MessagePart[];
}

type MessagePart =
  | { type: "text"; text: string }
  | { type: "tool-invocation"; toolInvocation: ToolInvocation }
  | { type: "source-url"; ... };
```

**Affected Files**:
- `surfsense_web/hooks/use-chat.ts`
- `surfsense_web/lib/utils.ts`
- `surfsense_web/contracts/types/chat.types.ts`
- `surfsense_web/components/chat/types.ts`

### 3. Tool Invocation State Changes

```typescript
// OLD (v4)
export interface ToolInvocation {
  state: "partial-call" | "call" | "result";
  // ...
}

// NEW (v5)
export interface ToolInvocation {
  state: "input-streaming" | "input-available" | "output-available";
  // ...
}
```

**State Mapping**:
- `"partial-call"` → `"input-streaming"`
- `"call"` → `"input-available"`
- `"result"` → `"output-available"`

**Affected File**: `surfsense_web/components/chat/types.ts:37-43`

### 4. Other Changes

- `processDataStream` removed
- `experimental_prepareRequestBody` → `prepareSendMessagesRequest` in transport config
- `providerMetadata` input → `providerOptions`

## Migration Steps

### Phase 1: Preparation (1-2 hours)

1. **Create migration branch**
   ```bash
   git checkout -b feature/ai-sdk-v5-migration
   ```

2. **Update dependencies**
   ```bash
   cd surfsense_web
   npm install ai@^5.0.95 @ai-sdk/react@latest
   ```

3. **Install v4 types alongside v5 for gradual migration** (optional)
   ```bash
   npm install --save-dev @ai-sdk/react-v4@npm:@ai-sdk/react@4
   ```

### Phase 2: Type Definitions (2-3 hours)

1. **Update `components/chat/types.ts`**
   - Change tool invocation states
   - Add new message part types

2. **Create message conversion utilities**
   ```typescript
   // lib/message-conversion.ts
   export function convertV4ToV5Message(v4Message: V4Message): UIMessage {
     return {
       id: v4Message.id,
       role: v4Message.role,
       parts: [{ type: "text", text: v4Message.content }],
     };
   }

   export function getMessageContent(message: UIMessage): string {
     return message.parts
       .filter((p) => p.type === "text")
       .map((p) => p.text)
       .join("");
   }
   ```

3. **Update type imports across files**
   - Change `Message` → `UIMessage` where appropriate

### Phase 3: useChat Migration (3-4 hours)

1. **Update researcher page** (`app/dashboard/[search_space_id]/researcher/[[...chat_id]]/page.tsx`)

   ```typescript
   const handler = useChat({
     api: `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chat`,
     streamProtocol: "data",
     messages: [],  // Changed from initialMessages
     headers: {
       ...(token && { Authorization: `Bearer ${token}` }),
     },
     // Remove static body, pass dynamic values in append()
   });

   // Update append calls to pass dynamic body
   const customHandlerAppend = async (message, chatRequestOptions) => {
     const newChatId = await createChat(...);
     if (newChatId) {
       // Pass dynamic values here
       handler.append(message, {
         body: {
           data: {
             search_space_id,
             selected_connectors: connectorTypes,
             research_mode: researchMode,
             search_mode: searchMode,
             document_ids_to_add_in_context: documentIds,
             top_k: topK,
           },
         },
       });
     }
   };
   ```

2. **Update message content access**
   ```typescript
   // OLD
   const content = message.content;

   // NEW
   const content = message.parts
     .filter(p => p.type === "text")
     .map(p => p.text)
     .join("");
   ```

### Phase 4: Component Updates (2-3 hours)

1. **Update ChatMessages component** to handle new message structure
2. **Update any component that accesses `message.content` directly**
3. **Update tool invocation rendering** to use new state names

### Phase 5: Database Compatibility (1-2 hours)

1. **Add runtime conversion for existing messages**
   - When loading chats from database, convert v4 messages to v5 format
   - When saving, decide whether to migrate data or keep conversion layer

2. **Update chat API handlers** if they expect specific message formats

### Phase 6: Testing (2-3 hours)

1. **Test new chat creation**
2. **Test loading existing chats** (backward compatibility)
3. **Test message streaming**
4. **Test tool invocations** if used
5. **Test all researcher page functionality**

## Files to Modify

| File | Changes Required |
|------|-----------------|
| `app/dashboard/[search_space_id]/researcher/[[...chat_id]]/page.tsx` | `initialMessages` → `messages`, body handling |
| `components/chat/types.ts` | Tool invocation states, add UIMessage type |
| `components/chat/ChatMessages.tsx` | Handle `parts` array |
| `components/chat/ChatFurtherQuestions.tsx` | Update message access |
| `hooks/use-chat.ts` | Update Message type imports |
| `hooks/use-chats.ts` | Update Message type imports |
| `lib/utils.ts` | Add message conversion utilities |
| `contracts/types/chat.types.ts` | Update type definitions |

## Rollback Plan

If issues arise after deployment:

1. Revert to previous package.json with `ai@^4.3.19`
2. Run `npm install` to restore v4 dependencies
3. Git revert the migration commit

## Resources

- [Official Migration Guide](https://ai-sdk.dev/docs/migration-guides/migration-guide-5-0)
- [Data Migration Guide](https://ai-sdk.dev/docs/migration-guides/migration-guide-5-0-data)
- [AI SDK 5 Migration MCP Server](https://github.com/vercel-labs/ai-sdk-5-migration-mcp-server)

## Estimated Total Time

- **Minimum**: 10-12 hours
- **With thorough testing**: 15-18 hours

## Recommendation

Consider this migration as a dedicated sprint task due to:
1. Multiple breaking changes
2. Risk to core chat functionality
3. Need for thorough testing
4. Potential database migration considerations

Start with Phase 1-2 to assess actual impact before committing to full migration.
