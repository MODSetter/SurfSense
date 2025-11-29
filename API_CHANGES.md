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
    {"id": 3, "reason": "Log not found or not owned by user"}
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

### Enhanced Error Reporting
Both bulk operations now provide detailed skip reasons:
- **bulk-retry**: "Log not eligible for retry" (covers: not found, not owned, or retry limit reached)
- **bulk-dismiss**: "Log not found or not owned by user"

### Improved Input Validation
- Empty `log_ids` arrays now return `400 Bad Request` instead of `404 Not Found`
- More appropriate HTTP status codes for different error scenarios
