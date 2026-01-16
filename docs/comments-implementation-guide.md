# Comments & Mentions Implementation Guide

> Implementation guide for adding Google Docs-style comments and @mentions to shared chats in SurfSense.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Decisions](#architecture-decisions)
3. [Database Design](#database-design)
4. [API Design](#api-design)
5. [Permission Model](#permission-model)
6. [Business Rules](#business-rules)
7. [File Structure](#file-structure)
8. [Implementation Phases](#implementation-phases)
9. [Testing Checklist](#testing-checklist)
10. [Out of Scope](#out-of-scope)

---

## Overview

### Problem Statement

When team members view a shared AI chat, they cannot discuss specific answers in place. Users currently have to screenshot or copy-paste the output into external tools (Slack/Teams) to ask questions or validate data. This context switching causes friction and fragments organizational knowledge.

### User Story

As a user, I want to be able to place and reply to comments on AI responses to let my team know my thoughts without leaving SurfSense.

### Solution

Users can place comments on AI chat responses and reply to existing comments, similar to Google Docs, but limited to a single level of nesting per AI response.

---

## Architecture Decisions

### Threading Model

```
AI Response (message_id: 123)
├── Comment A (parent_id: NULL)      ← Top-level comment
│   ├── Reply A1 (parent_id: A)      ← Reply
│   ├── Reply A2 (parent_id: A)      ← Reply
│   └── Reply A3 (parent_id: A)      ← Reply
├── Comment B (parent_id: NULL)      ← Top-level comment
│   └── Reply B1 (parent_id: B)      ← Reply
└── Comment C (parent_id: NULL)      ← Top-level comment (no replies)
```

- **Multiple top-level comments** allowed per AI response
- **One level of nesting** (replies to comments, but no replies to replies)
- API enforces nesting limit, not DB constraint

### Comment Anchoring

- Comments attach to **AI responses only** (not user messages)
- Comments attach to **entire message** (not text selection)
- Validated by checking `message.role == 'assistant'`

### @Mentions

- **Storage format:** `@[uuid]` in raw content
- **Display format:** `@Display Name` in rendered content
- Mentions extracted and stored in separate table for notifications
- Only search space members can be mentioned

### Read/Unread Mentions

- Simple boolean on mention record
- Marked read when user clicks the mention notification
- No automatic read-on-view (keep it simple)

### Cascade Behavior

- Deleting a comment deletes all its replies (DB CASCADE)
- Deleting/regenerating a message deletes its comments (DB CASCADE)

### Backend-First Architecture

- All business logic in backend
- Frontend is a thin consumer
- Backend returns computed fields: `can_edit`, `can_delete`, `is_edited`, `content_rendered`

---

## Database Design

### Table: `chat_comments`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `SERIAL` | PK | Primary key |
| `message_id` | `INTEGER` | FK → `new_chat_messages(id)` ON DELETE CASCADE, NOT NULL | Which AI response |
| `parent_id` | `INTEGER` | FK → `chat_comments(id)` ON DELETE CASCADE, NULLABLE | NULL = top-level, otherwise = reply |
| `author_id` | `UUID` | FK → `user(id)` ON DELETE SET NULL | Who wrote it |
| `content` | `TEXT` | NOT NULL | Plain text, may contain `@[uuid]` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | Creation time |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | Last edit time |

**Indexes:**
- `idx_comments_message_id` on `message_id`
- `idx_comments_parent_id` on `parent_id`
- `idx_comments_author_id` on `author_id`
- `idx_comments_created_at` on `created_at`

### Table: `chat_comment_mentions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `SERIAL` | PK | Primary key |
| `comment_id` | `INTEGER` | FK → `chat_comments(id)` ON DELETE CASCADE, NOT NULL | Which comment |
| `mentioned_user_id` | `UUID` | FK → `user(id)` ON DELETE CASCADE, NOT NULL | Who was mentioned |
| `read` | `BOOLEAN` | NOT NULL, DEFAULT FALSE | Has user seen it |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | When mentioned |

**Constraints:**
- `UNIQUE (comment_id, mentioned_user_id)` - Can't mention same person twice

**Indexes:**
- `idx_mentions_user_unread` on `(mentioned_user_id) WHERE read = FALSE` (partial index)
- `idx_mentions_comment_id` on `comment_id`

### Schema Diagram

```
new_chat_messages (existing)
         │
         │ 1:N
         ▼
┌──────────────────────────────────┐
│       chat_comments              │
├──────────────────────────────────┤
│ id (PK)                          │
│ message_id (FK)                  │
│ parent_id (FK, self-ref)         │
│ author_id (FK → user)            │
│ content                          │
│ created_at                       │
│ updated_at                       │
└──────────────────────────────────┘
         │
         │ 1:N
         ▼
┌──────────────────────────────────┐
│   chat_comment_mentions          │
├──────────────────────────────────┤
│ id (PK)                          │
│ comment_id (FK)                  │
│ mentioned_user_id (FK → user)    │
│ read                             │
│ created_at                       │
└──────────────────────────────────┘
```

---

## API Design

### Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/v1/messages/{message_id}/comments` | List comments with replies |
| `POST` | `/api/v1/messages/{message_id}/comments` | Create top-level comment |
| `POST` | `/api/v1/comments/{comment_id}/replies` | Reply to a comment |
| `PUT` | `/api/v1/comments/{comment_id}` | Edit comment (author only) |
| `DELETE` | `/api/v1/comments/{comment_id}` | Delete comment + replies |
| `GET` | `/api/v1/users/me/mentions` | List user's mentions |
| `POST` | `/api/v1/mentions/{mention_id}/read` | Mark mention as read |
| `POST` | `/api/v1/users/me/mentions/read-all` | Mark all mentions read |

### Request Schemas

**Create/Update Comment:**
```json
{
  "content": "string (1-5000 chars)"
}
```

### Response Schemas

**Comment Response:**
```json
{
  "id": 1,
  "message_id": 123,
  "content": "Is this accurate? @[uuid-here]",
  "content_rendered": "Is this accurate? @John Doe",
  "author": {
    "id": "uuid",
    "display_name": "Jane Smith",
    "avatar_url": "https://...",
    "email": "jane@example.com"
  },
  "created_at": "2024-01-15T10:42:00Z",
  "updated_at": "2024-01-15T10:42:00Z",
  "is_edited": false,
  "can_edit": true,
  "can_delete": true,
  "reply_count": 2,
  "replies": [
    {
      "id": 2,
      "content": "Yes, verified",
      "content_rendered": "Yes, verified",
      "author": { ... },
      "created_at": "...",
      "updated_at": "...",
      "is_edited": false,
      "can_edit": false,
      "can_delete": false
    }
  ]
}
```

**Comment List Response:**
```json
{
  "comments": [ ... ],
  "total_count": 5
}
```

**Mention Response:**
```json
{
  "id": 1,
  "read": false,
  "created_at": "2024-01-15T10:42:00Z",
  "comment": {
    "id": 5,
    "content_preview": "Hey, can you check...",
    "author": {
      "display_name": "John Doe",
      "avatar_url": "..."
    },
    "created_at": "..."
  },
  "context": {
    "thread_id": 123,
    "thread_title": "Q3 Analysis",
    "message_id": 456,
    "search_space_id": 1,
    "search_space_name": "Finance Team"
  }
}
```

**Mention List Response:**
```json
{
  "mentions": [ ... ],
  "unread_count": 3
}
```

---

## Permission Model

### New Permissions

Add to `Permission` enum in `db.py`:

| Permission | Value |
|------------|-------|
| `COMMENTS_CREATE` | `"comments:create"` |
| `COMMENTS_READ` | `"comments:read"` |
| `COMMENTS_DELETE` | `"comments:delete"` |

### Default Role Assignments

| Role | `comments:read` | `comments:create` | `comments:delete` |
|------|-----------------|-------------------|-------------------|
| Owner | ✅ | ✅ | ✅ |
| Admin | ✅ | ✅ | ✅ |
| Editor | ✅ | ✅ | ❌ |
| Viewer | ✅ | ✅ | ❌ |

### Authorization Rules

| Action | Who Can Do It |
|--------|---------------|
| Read comments | Anyone with `comments:read` |
| Create comment | Anyone with `comments:create` |
| Create reply | Anyone with `comments:create` |
| Edit comment | Author only |
| Delete own comment | Author |
| Delete any comment | Anyone with `comments:delete` |

---

## Business Rules

### Validation Rules

1. **Message must be AI response:** `message.role == 'assistant'`
2. **Reply parent must be top-level:** `parent.parent_id IS NULL`
3. **Content not empty:** 1-5000 characters
4. **Mentioned users must be search space members**

### Computed Fields (Backend Returns)

| Field | Logic |
|-------|-------|
| `is_edited` | `updated_at > created_at` |
| `can_edit` | `comment.author_id == current_user.id` |
| `can_delete` | `author_id == user.id OR has_permission("comments:delete")` |
| `content_rendered` | Replace `@[uuid]` with `@Display Name` |
| `reply_count` | Count of replies |

### Mention Processing

1. On comment create/update, parse `@[uuid]` patterns from content
2. Validate each UUID is a member of the search space
3. Insert/update records in `chat_comment_mentions`
4. Invalid UUIDs: silently ignore (don't create mention record)

### Error Responses

| Scenario | HTTP Status | Message |
|----------|-------------|---------|
| Message not found | 404 | "Message not found" |
| Message is not AI response | 400 | "Comments can only be added to AI responses" |
| Comment not found | 404 | "Comment not found" |
| Cannot reply to reply | 400 | "Cannot reply to a reply" |
| Not authorized to edit | 403 | "You can only edit your own comments" |
| Not authorized to delete | 403 | "You do not have permission to delete this comment" |
| Mention not found | 404 | "Mention not found" |

---

## File Structure

```
surfsense_backend/app/
├── routes/
│   └── comments_routes.py         # All comment endpoints
│
├── services/
│   └── comments_service.py        # Business logic + DB access
│
├── schemas/
│   └── comments.py                # Request/response schemas
│
├── utils/
│   └── comments.py                # Mention parsing, helpers
│
├── db.py                          # Add models (ChatComment, ChatCommentMention)
│
└── alembic/versions/
    └── XX_add_comments_tables.py  # Migration
```

## Implementation Phases

### Phase 1: Foundation (P0)

| Task | Description |
|------|-------------|
| 1.1 | Create `chat_comments` table migration |
| 1.2 | Create `chat_comment_mentions` table migration |
| 1.3 | Add `ChatComment` model to `db.py` |
| 1.4 | Add `ChatCommentMention` model to `db.py` |
| 1.5 | Add comment permissions to `Permission` enum |
| 1.6 | Update `DEFAULT_ROLE_PERMISSIONS` |

### Phase 2: Core CRUD (P0)

| Task | Description |
|------|-------------|
| 2.1 | Create Pydantic schemas in `schemas/comments.py` |
| 2.2 | Implement `GET /messages/{id}/comments` |
| 2.3 | Implement `POST /messages/{id}/comments` |
| 2.4 | Implement `POST /comments/{id}/replies` |
| 2.5 | Implement `PUT /comments/{id}` |
| 2.6 | Implement `DELETE /comments/{id}` |

### Phase 3: Mentions (P1)

| Task | Description |
|------|-------------|
| 3.1 | Create mention parser in `utils/comments.py` |
| 3.2 | Validate mentioned users are search space members |
| 3.3 | Insert mentions on comment create/update |
| 3.4 | Return `content_rendered` with names resolved |
| 3.5 | Implement `GET /users/me/mentions` |
| 3.6 | Implement `POST /mentions/{id}/read` |
| 3.7 | Implement `POST /users/me/mentions/read-all` |

### Phase 4: Authorization (P1)

| Task | Description |
|------|-------------|
| 4.1 | Check `comments:read` on list endpoint |
| 4.2 | Check `comments:create` on create/reply |
| 4.3 | Check author-only on edit |
| 4.4 | Check author OR `comments:delete` on delete |
| 4.5 | Validate message is AI response |
| 4.6 | Validate parent is top-level |

### Phase 5: Response Enrichment (P1)

| Task | Description |
|------|-------------|
| 5.1 | Return `can_edit` per comment |
| 5.2 | Return `can_delete` per comment |
| 5.3 | Return `is_edited` |
| 5.4 | Return author info (name, avatar, email fallback) |
| 5.5 | Return `reply_count` per top-level comment |

### Phase 6: Edge Cases (P2)

| Task | Description |
|------|-------------|
| 6.1 | Handle deleted user (author_id SET NULL) |
| 6.2 | Handle mention of user no longer in search space |
| 6.3 | Clear error when replying to deleted comment |

---

## Testing Checklist (will be done manual)

### Functional Tests

- [ ] Create comment on AI response
- [ ] Create comment on user message (should fail)
- [ ] Reply to comment
- [ ] Reply to reply (should fail)
- [ ] Edit own comment
- [ ] Edit other's comment (should fail)
- [ ] Delete own comment (and verify replies deleted)
- [ ] Delete other's comment as owner/admin
- [ ] Delete other's comment as editor/viewer (should fail)

### Mention Tests

- [ ] Mention valid user creates mention record
- [ ] Mention invalid UUID is ignored
- [ ] Mention non-member is ignored
- [ ] `content_rendered` shows display names
- [ ] List mentions returns correct data
- [ ] Mark mention read updates `read` flag
- [ ] Mark all read updates all mentions

### Edge Case Tests

- [ ] Comment with 10+ replies scrolls properly (frontend)
- [ ] Delete parent comment cascades to replies
- [ ] Regenerate AI response deletes comments
- [ ] Comment on one-word AI response (frontend min height)
- [ ] User A deletes comment while User B replies → clear error

### Permission Tests

- [ ] Viewer can read comments
- [ ] Viewer can create comments
- [ ] Viewer cannot delete other's comments
- [ ] Owner can delete any comment

---

## Out of Scope

The following are explicitly NOT included in v1:

| Feature | Reason |
|---------|--------|
| Multiple threads per message | Simplicity |
| Text selection comments | Complexity |
| Rich text (bold/italic/images) | Complexity |
| Email/push notifications | Infrastructure |
| Emoji reactions | Scope |
| Comment on user messages | Focus on AI responses |
| Nested replies (> 2 levels) | UX complexity |

---

## Future Considerations (Not Now)

These are documented for future reference but NOT to be implemented now:

1. **Stale comment detection:** Store `message_content_hash` to detect if AI response changed
2. **Real-time sync:** Electric-SQL integration for live updates
3. **Notification center:** Dedicated page for all notifications
4. **Email digests:** Periodic email summaries of mentions
5. **Comment reactions:** Thumbs up, etc.

---

## References

- Existing patterns: `routes/new_chat_routes.py`, `services/connector_service.py`
- Permission system: `db.py` (Permission enum, DEFAULT_ROLE_PERMISSIONS)
- Schema patterns: `schemas/new_chat.py`

# Important rules

- Never do actions in bulk , you will always need my approval before doing something i dod not specifically mention in the prompt
- After each item task , we need to commit , for the backend we need to make sure , there are no ruff errors (ruff check, ruff format); for the frontend we need to run pnpm format:fix at web project.
- Commits should have minimal message and use --no-verify flag