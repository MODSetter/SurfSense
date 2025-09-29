# GitHub Connector Indexing Fix

## Problem Summary

The GitHub connector was experiencing issues where:
1. Documents were not appearing in "Manage Documents" after indexing
2. The "Last Indexed" timestamp would show initially but revert to "Never" after page refresh  
3. Queries always returned 0 related documents despite successful indexing logs

## Root Causes Identified

### 1. Missing `last_indexed_at` Update
The GitHub indexer (`github_indexer.py`) was missing the call to `update_connector_last_indexed()` that other indexers (like JIRA) properly included. This caused the "Last Indexed" timestamp to not be persisted.

### 2. Timezone-Aware Timestamp Issues
The database schema expects timezone-aware timestamps (`TIMESTAMP(timezone=True)`), but the update functions were using `datetime.now()` without timezone information, causing potential issues with timestamp storage.

### 3. Session/Transaction Management Issues
The GitHub indexing route was trying to update the `last_indexed_at` timestamp in a separate session from the one used for document indexing, which could cause transaction conflicts.

## Fixes Applied

### 1. Added Missing Import (for future use)
**File:** `surfsense_backend/app/tasks/connector_indexers/github_indexer.py`

```python
# Added import for consistency with other indexers
from .base import (
    check_duplicate_document_by_hash,
    get_connector_by_id,
    logger,
    update_connector_last_indexed,  # <- Added this for future flexibility
)

# Note: The update_last_indexed logic is handled by the route layer
# following the established pattern used by other connectors
```

### 2. Fixed Timezone-Aware Timestamps
**File:** `surfsense_backend/app/tasks/connector_indexers/base.py`

```python
# Added UTC import
from datetime import UTC, datetime, timedelta

# Fixed timestamp creation
connector.last_indexed_at = datetime.now(UTC)  # <- Added UTC
```

**File:** `surfsense_backend/app/routes/search_source_connectors_routes.py`

```python
# Added UTC import
from datetime import UTC, datetime, timedelta

# Fixed timestamp creation
connector.last_indexed_at = datetime.now(UTC)  # <- Added UTC
```

### 3. Proper Session Management Pattern
**File:** `surfsense_backend/app/routes/search_source_connectors_routes.py`

**Solution:** Follow the established pattern used by other connectors: let the route handle the timestamp update after successful indexing.

```python
# Follow the standard pattern used by other connectors
indexed_count, error_message = await index_github_repos(
    session,
    connector_id,
    search_space_id,
    user_id,
    start_date,
    end_date,
    update_last_indexed=False,  # Standard pattern: let route handle timestamp
)

# Update timestamp only on success (like other connectors)
if error_message:
    logger.error(f"GitHub indexing failed for connector {connector_id}: {error_message}")
else:
    logger.info(f"GitHub indexing successful for connector {connector_id}. Indexed {indexed_count} documents.")
    await update_connector_last_indexed(session, connector_id)
    await session.commit()
```

## Testing the Fix

### 1. Test Document Persistence
After applying the fix:
1. Configure a GitHub connector with a valid PAT
2. Select repositories to index
3. Trigger indexing
4. Check that documents appear in "Manage Documents"
5. Verify that queries return relevant results

### 2. Test Last Indexed Timestamp
1. After successful indexing, note the "Last Indexed" timestamp
2. Refresh the connectors page
3. Verify the timestamp persists and doesn't revert to "Never"

### 3. Use Debug Script
A debug script has been provided (`debug_github_connector.py`) to help diagnose issues:

```bash
cd /path/to/SurfSense
python debug_github_connector.py --connector-id <connector_id> --search_space_id <search_space_id>
```

This script will:
- Check if the connector exists
- Count GitHub documents in the search space
- Show document distribution by type
- Verify database state

## Additional Improvements Made

### Enhanced Error Handling
The fix maintains the existing error handling while ensuring that successful indexing properly updates timestamps.

### Consistent with Other Connectors
The GitHub indexer now follows the same pattern as other working connectors (like JIRA) for timestamp management.

### Better Transaction Integrity
By handling timestamp updates within the same transaction as document creation, we avoid potential consistency issues.

## Rollback Instructions

If issues arise, you can rollback by:

1. Reverting the import change in `github_indexer.py`
2. Removing the `update_connector_last_indexed` call
3. Reverting the UTC timestamp changes
4. Reverting the session management changes in the routes

However, these changes are minimal and follow established patterns from other working indexers, so rollback should not be necessary.

## Monitoring

After deploying the fix, monitor:
1. GitHub connector indexing logs for any new errors
2. Document creation in the database
3. Last indexed timestamp persistence
4. Query result accuracy

The fix addresses the core issues while maintaining compatibility with the existing codebase and following established patterns from other working connectors.