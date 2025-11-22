# SurfSense Security Model

This document describes the security model and permissions system for SurfSense, with special focus on the Space Sharing feature.

## Table of Contents

- [Overview](#overview)
- [Space Permissions Model](#space-permissions-model)
- [Authentication & Authorization](#authentication--authorization)
- [Security Best Practices](#security-best-practices)
- [Security Testing](#security-testing)
- [Threat Model](#threat-model)

## Overview

SurfSense implements a multi-layered security model with:

1. **Authentication**: JWT-based token authentication for all API endpoints
2. **Authorization**: Role-based access control (RBAC) with owner and superuser roles
3. **Data Isolation**: User-scoped data access with explicit sharing controls
4. **Input Validation**: Comprehensive validation of all user inputs
5. **Defense in Depth**: Multiple layers of security checks

## Space Permissions Model

### Space Types

Search spaces in SurfSense can be either **private** or **public**:

#### Private Spaces (`is_public = false`)
- **Default**: All newly created spaces are private
- **Visibility**: Only visible to the owner
- **Access**: Only the owner (and superusers) can read or write
- **Use Case**: Personal knowledge bases, sensitive data

#### Public Spaces (`is_public = true`)
- **Visibility**: Visible to all authenticated users
- **Read Access**: Any authenticated user can view and query the space
- **Write Access**: **ONLY** the owner and superusers can modify
- **Use Case**: Team knowledge bases, shared documentation

### Permission Matrix

| Action | Owner | Superuser | Non-Owner (Private) | Non-Owner (Public) |
|--------|-------|-----------|---------------------|-------------------|
| **View Space** | ✅ | ✅ | ❌ | ✅ |
| **Query/Search** | ✅ | ✅ | ❌ | ✅ |
| **Add Documents** | ✅ | ✅ | ❌ | ❌ |
| **Upload Files** | ✅ | ✅ | ❌ | ❌ |
| **Create Connectors** | ✅ | ✅ | ❌ | ❌ |
| **Index Content** | ✅ | ✅ | ❌ | ❌ |
| **Update Space** | ✅ | ✅ | ❌ | ❌ |
| **Delete Space** | ✅ | ✅ | ❌ | ❌ |
| **Share Space** | ❌ | ✅ | ❌ | ❌ |
| **Unshare Space** | ❌ | ✅ | ❌ | ❌ |

### Key Security Principles

#### 1. Read-Only Public Spaces

**Critical Security Requirement**: Public spaces MUST be read-only for non-owners.

**Rationale**:
- Prevents unauthorized users from polluting shared knowledge bases
- Protects against malicious content injection
- Maintains data integrity for shared resources

**Implementation**:
- `verify_space_write_permission()` function checks write access
- Applied to ALL endpoints that modify space content:
  - Document creation (`POST /documents`)
  - File uploads (`POST /documents/fileupload`)
  - Connector creation (`POST /search-source-connectors`)
  - Content indexing (`POST /search-source-connectors/{id}/index`)

**Testing**:
```python
def test_cannot_add_documents_to_public_space():
    # Non-owner attempts to add documents to public space
    response = client.post("/api/v1/documents", ...)
    assert response.status_code == 403
    assert "read-only" in response.json()["detail"].lower()
```

#### 2. Superuser-Only Sharing

**Critical Security Requirement**: Only superusers can make spaces public or private.

**Rationale**:
- Prevents accidental exposure of sensitive data
- Maintains centralized control over shared resources
- Protects against social engineering attacks

**Implementation**:
- `POST /searchspaces/{id}/share` endpoint
- Checks `user.is_superuser` before allowing share operation
- Returns 403 Forbidden for non-superusers

#### 3. Owner Privileges

**Principle**: Space owners always have full control over their spaces.

**Rationale**:
- Users should always be able to manage their own content
- Even public spaces remain under owner's control
- Prevents orphaned or unmanageable spaces

**Exception**: Sharing/unsharing is superuser-only, even for owners.

## Authentication & Authorization

### JWT Token-Based Authentication

All API endpoints (except public routes) require a valid JWT token:

```typescript
Authorization: Bearer <jwt_token>
```

**Token Storage**:
- Frontend: `localStorage` (key: `AUTH_TOKEN_KEY`)
- Token includes user ID and superuser status

**Token Validation**:
- Performed on every request via `current_active_user` dependency
- Invalid/expired tokens return 401 Unauthorized

### Role-Based Access Control (RBAC)

Two primary roles:

1. **Regular User**:
   - Full control over owned resources
   - Read-only access to public spaces
   - Cannot share spaces

2. **Superuser** (`is_superuser = true`):
   - All regular user permissions
   - Can share/unshare any space
   - Can modify any space (including public ones)
   - Administrative access to system settings

## Security Best Practices

### Backend Development

1. **Always use permission checks**:
   ```python
   # For write operations
   await verify_space_write_permission(session, space_id, user)

   # For read operations with ownership requirement
   await check_ownership(session, Model, id, user)
   ```

2. **Never trust client-side checks**:
   - Frontend visibility (`user?.is_superuser`) is for UX only
   - Always validate permissions server-side

3. **Use prepared statements**:
   - SQLAlchemy ORM automatically prevents SQL injection
   - For raw queries, use parameterized statements

4. **Validate all inputs**:
   - Use Pydantic models for request validation
   - Sanitize file uploads (magic byte validation)
   - Limit file sizes

5. **Use session.get() for primary keys**:
   ```python
   # Efficient and secure
   space = await session.get(SearchSpace, space_id)
   ```

### Frontend Development

1. **Use centralized API client**:
   ```typescript
   import { apiPost } from '@/lib/api-client';

   // Automatic error handling and auth
   await apiPost('/api/v1/documents', data);
   ```

2. **Handle errors gracefully**:
   ```typescript
   try {
     await apiRequest('/endpoint', { ... });
   } catch (error) {
     if (error instanceof ApiError) {
       // Handle specific error codes
     }
   }
   ```

3. **Never store sensitive data in localStorage**:
   - Only store non-sensitive tokens
   - Clear tokens on logout

4. **Use TypeScript for type safety**:
   - Prevents many runtime errors
   - Catches API mismatches at compile time

## Security Testing

### Test Coverage Requirements

All security-critical features must have:

1. **Unit Tests**: Test individual permission checks
2. **Integration Tests**: Test full request/response cycle
3. **E2E Tests**: Test user flows in browser

### Critical Test Scenarios

#### Space Sharing Tests

```python
# 1. Sharing requires superuser
def test_share_space_requires_superuser():
    response = client.post("/api/v1/searchspaces/1/share",
        headers={"Authorization": f"Bearer {normal_user_token}"})
    assert response.status_code == 403

# 2. Public spaces are read-only
def test_cannot_add_documents_to_public_space():
    response = client.post("/api/v1/documents", ...)
    assert response.status_code == 403

# 3. Public spaces are discoverable
def test_public_spaces_visible_to_all_users():
    response = client.get("/api/v1/searchspaces", ...)
    assert public_space in response.json()
```

### Security Audit Checklist

Before deploying:

- [ ] All write endpoints use `verify_space_write_permission`
- [ ] Sharing endpoint checks `is_superuser`
- [ ] Database migration applied successfully
- [ ] No NULL values in `is_public` column
- [ ] Indexes exist for performance
- [ ] All tests passing
- [ ] No hardcoded credentials
- [ ] Dependencies up to date (no critical vulnerabilities)

## Threat Model

### Threats Mitigated

1. **Unauthorized Data Access**:
   - **Threat**: User A accessing User B's private space
   - **Mitigation**: Server-side ownership checks on all endpoints

2. **Data Pollution**:
   - **Threat**: Non-owner injecting malicious content into public space
   - **Mitigation**: Read-only enforcement via `verify_space_write_permission`

3. **Privilege Escalation**:
   - **Threat**: Regular user sharing spaces without authorization
   - **Mitigation**: Superuser-only sharing endpoint

4. **Session Hijacking**:
   - **Threat**: Attacker stealing JWT token
   - **Mitigation**: HTTPS-only, token expiration, secure storage

5. **SQL Injection**:
   - **Threat**: Malicious input executing arbitrary SQL
   - **Mitigation**: SQLAlchemy ORM, parameterized queries

6. **File Upload Attacks**:
   - **Threat**: Malicious file uploads (malware, scripts)
   - **Mitigation**: File type validation, magic byte checking, size limits

### Known Limitations

1. **Token Storage**: Tokens stored in localStorage are vulnerable to XSS
   - **Future**: Consider httpOnly cookies

2. **No Rate Limiting**: API endpoints not rate-limited
   - **Future**: Implement per-user rate limits

3. **No Audit Logging**: Administrative actions not logged
   - **Future**: Add security events table

## Database Schema

### SearchSpace Model

```python
class SearchSpace(Base):
    __tablename__ = 'searchspaces'

    id = Column(Integer, primary_key=True)
    user_id = Column(UUID, ForeignKey('user.id'), nullable=False)
    name = Column(String, nullable=False)

    # Security-critical field
    is_public = Column(
        Boolean,
        nullable=False,
        default=False,  # Secure default
        index=True      # Performance optimization
    )

    # Composite index for common query
    __table_args__ = (
        Index('ix_searchspaces_user_public', 'user_id', 'is_public'),
    )
```

### Migration Safety

Migration 43 adds `is_public` with:
- **Non-nullable**: Prevents NULL confusion
- **Default false**: Secure by default (private)
- **Server default**: Ensures existing rows get false
- **Indexed**: Maintains query performance

## Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** create a public GitHub issue
2. Email security contact: [security@surfsense.dev](mailto:security@surfsense.dev)
3. Include:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We aim to respond within 48 hours.

## Version History

- **v0.0.8-LV01** (2025-11-22): Added space sharing feature with read-only public spaces
- **Previous**: Private spaces only

---

**Last Updated**: 2025-11-22
**Maintained By**: SurfSense Security Team
