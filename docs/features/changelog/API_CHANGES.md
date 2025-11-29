# API Breaking Changes

This document tracks breaking changes to the SurfSense API.

## 2025-01-XX - Bulk Operations Response Format Update

### Affected Endpoints
- `POST /api/v1/logs/bulk-dismiss`

### Breaking Change Description

The `total` field in the response now includes both successfully processed items AND skipped items, whereas previously it only counted successfully processed items.

**Previous Behavior:**
```json
{
  "dismissed": [1, 2, 3],
  "total": 3
}
```

**New Behavior:**
```json
{
  "dismissed": [1, 2],
  "skipped": [
    {"id": 3, "reason": "Log could not be dismissed"}
  ],
  "total": 3
}
```

### Rationale

This change improves API consistency between `bulk-dismiss` and `bulk-retry` endpoints, both of which now:
- Return explicit `skipped` arrays with reasons
- Include skipped items in the `total` count
- Provide transparent feedback about which operations failed and why

### Migration Guide

If your code relies on the `total` field to represent only successfully dismissed logs:

**Before:**
```typescript
const dismissedCount = result.total; // Only dismissed logs
```

**After:**
```typescript
const dismissedCount = result.dismissed.length; // Explicitly count dismissed logs
const totalProcessed = result.total; // Total attempted (dismissed + skipped)
```

### Impact

**Low to Medium** - Most client code should continue working, but any logic that uses the `total` field for business decisions may need updates.

## Related Changes

### Granular Skip Reason Categorization
Both bulk operations now use specific skip reasons defined as an Enum for better debugging:

**SkipReason Enum Values:**
- `LOG_NOT_FOUND` - "Log not found"
- `NOT_OWNER` - "Not authorized to modify this log"
- `RETRY_LIMIT_REACHED` - "Maximum retry limit reached"
- `INVALID_STATUS` - "Log status not eligible for this operation"
- `ALREADY_DISMISSED` - "Log already dismissed"

**bulk-retry skip reasons:**
- `LOG_NOT_FOUND`: Log ID does not exist in database
- `NOT_OWNER`: User does not have permission to modify this log
- `RETRY_LIMIT_REACHED`: Log has already been retried 3 times (maximum)
- `INVALID_STATUS`: Log status is not FAILED (e.g., IN_PROGRESS, SUCCESS, DISMISSED)

**bulk-dismiss skip reasons:**
- `LOG_NOT_FOUND`: Log ID does not exist in database
- `NOT_OWNER`: User does not have permission to modify this log
- `ALREADY_DISMISSED`: Log is already in DISMISSED status

**Example bulk-retry Response:**
```json
{
  "retried": [1, 2],
  "skipped": [
    {"id": 3, "reason": "Log not found"},
    {"id": 4, "reason": "Not authorized to modify this log"},
    {"id": 5, "reason": "Maximum retry limit reached"},
    {"id": 6, "reason": "Log status not eligible for this operation"}
  ],
  "total": 6
}
```

**Example bulk-dismiss Response:**
```json
{
  "dismissed": [1, 2],
  "skipped": [
    {"id": 3, "reason": "Log not found"},
    {"id": 4, "reason": "Not authorized to modify this log"},
    {"id": 5, "reason": "Log already dismissed"}
  ],
  "total": 5
}
```

This granular categorization:
- Enables precise client-side debugging and error handling
- Distinguishes between multiple failure scenarios:
  - "not found" vs "permission denied" vs "limit reached" vs "invalid status"
  - "already dismissed" for idempotent operations
- Prevents incorrect categorization (e.g., marking invalid status logs as not found)
- Adds status checks to UPDATE operations for correctness
- Uses type-safe Enum pattern aligned with existing codebase (LogLevel, LogStatus)
- Provides clear, actionable feedback to users and developers
- Maintains API consistency between bulk operations

### Improved Input Validation
- Empty `log_ids` arrays now return `400 Bad Request` instead of `404 Not Found`
- More appropriate HTTP status codes for different error scenarios
