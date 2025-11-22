---
name: Audit Logging Expansion
about: Expand security audit logging and observability for compliance and incident response
title: 'Expand Security Audit Logging'
labels: 'security, observability, compliance'
assignees: ''
---

## Summary
Comprehensively review and expand security audit logging across all backend and authentication endpoints to support incident investigation, compliance requirements, and anomaly detection.

## Motivation
Current audit logging covers baseline actions (sharing, failed writes), but comprehensive security logging requires:
- **Incident Response**: Detailed audit trail for security investigations
- **Compliance**: Meet regulatory requirements (GDPR, SOC 2, etc.)
- **Anomaly Detection**: Identify suspicious patterns (brute force, privilege escalation)
- **Accountability**: Track all security-relevant actions with user context

### Current Gaps
- Permission failures may not be consistently logged
- Authentication errors lack detailed context
- Repetitive failed operations (uploads, API calls) not tracked
- No correlation IDs for tracking related events
- Insufficient structured logging for automated analysis

## Proposed Implementation

### 1. Authentication Events
```python
# surfsense_backend/app/routes/auth_routes.py
from app.utils.audit_logger import log_security_event

@router.post("/login")
async def login(credentials: LoginCredentials):
    try:
        user = await authenticate_user(credentials)

        # Log successful login
        log_security_event(
            event_type="auth.login.success",
            user_id=user.id,
            username=user.email,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            metadata={"method": "password"}
        )

        return {"token": create_token(user)}

    except InvalidCredentialsError:
        # Log failed login attempt
        log_security_event(
            event_type="auth.login.failed",
            username=credentials.email,  # No user_id available
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            metadata={"reason": "invalid_credentials"}
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
```

### 2. Permission Denied Events
```python
# surfsense_backend/app/utils/check_ownership.py
def check_ownership(session, model, resource_id, user):
    resource = await session.get(model, resource_id)

    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    if resource.user_id != user.id and not user.is_superuser:
        # Log permission denied
        log_security_event(
            event_type="authz.permission_denied",
            user_id=user.id,
            username=user.email,
            resource_type=model.__name__,
            resource_id=resource_id,
            attempted_action="access",
            ip_address=get_client_ip(),
            metadata={
                "owner_id": resource.user_id,
                "is_superuser": user.is_superuser
            }
        )

        raise HTTPException(status_code=403, detail="Permission denied")

    return resource
```

### 3. Suspicious Activity Detection
```python
# surfsense_backend/app/middleware/security_middleware.py
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimitTracker:
    """Track failed attempts per user/IP for anomaly detection"""

    def __init__(self):
        self.failed_attempts = defaultdict(list)

    def record_failure(self, identifier: str, event_type: str):
        """Record a failed attempt and check for suspicious patterns"""
        now = datetime.utcnow()
        attempts = self.failed_attempts[identifier]

        # Add current attempt
        attempts.append({"timestamp": now, "event_type": event_type})

        # Clean old attempts (> 1 hour)
        attempts = [a for a in attempts if now - a["timestamp"] < timedelta(hours=1)]
        self.failed_attempts[identifier] = attempts

        # Check for suspicious patterns
        if len(attempts) >= 5:  # 5+ failures in 1 hour
            log_security_event(
                event_type="security.suspicious_activity",
                identifier=identifier,
                metadata={
                    "pattern": "repeated_failures",
                    "count": len(attempts),
                    "window": "1h",
                    "events": [a["event_type"] for a in attempts]
                },
                severity="warning"
            )
```

### 4. Data Access Logging
```python
# surfsense_backend/app/routes/documents_routes.py
@router.get("/documents/{document_id}")
async def get_document(document_id: int, user: User = Depends(current_active_user)):
    document = await get_document_with_permission_check(document_id, user)

    # Log sensitive data access
    if document.contains_pii or document.is_confidential:
        log_security_event(
            event_type="data.access.sensitive",
            user_id=user.id,
            resource_type="document",
            resource_id=document_id,
            metadata={
                "contains_pii": document.contains_pii,
                "is_confidential": document.is_confidential,
                "access_reason": request.headers.get("X-Access-Reason")
            }
        )

    return document
```

### 5. Centralized Audit Logger
```python
# surfsense_backend/app/utils/audit_logger.py
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from app.db import AuditLog, get_async_session

logger = logging.getLogger("audit")

async def log_security_event(
    event_type: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    attempted_action: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    severity: str = "info"
):
    """
    Log security-relevant event to both database and log file.

    Args:
        event_type: Type of event (e.g., "auth.login.failed", "authz.permission_denied")
        user_id: ID of user performing action (if authenticated)
        username: Username/email (even if auth failed)
        ip_address: Client IP address
        user_agent: Client user agent
        resource_type: Type of resource accessed (e.g., "SearchSpace", "Document")
        resource_id: ID of resource
        attempted_action: Action attempted (e.g., "access", "delete", "modify")
        metadata: Additional contextual data
        severity: Event severity (info, warning, error, critical)
    """
    timestamp = datetime.utcnow()

    audit_entry = {
        "timestamp": timestamp.isoformat(),
        "event_type": event_type,
        "user_id": user_id,
        "username": username,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "attempted_action": attempted_action,
        "metadata": metadata or {},
        "severity": severity
    }

    # Log to structured log file
    logger.log(
        getattr(logging, severity.upper(), logging.INFO),
        json.dumps(audit_entry)
    )

    # Optionally store in database for querying
    async with get_async_session() as session:
        db_audit = AuditLog(**audit_entry)
        session.add(db_audit)
        await session.commit()
```

## Events to Log

### Authentication
- [x] ✅ Already logged: Login success/failure
- [ ] Password reset requested
- [ ] Password reset completed
- [ ] Email verification
- [ ] Account locked (too many failures)
- [ ] MFA enabled/disabled
- [ ] API key created/revoked

### Authorization
- [ ] Permission denied (all cases)
- [ ] Role/permission changed
- [ ] Superuser action performed
- [ ] Cross-tenant access attempt

### Data Operations
- [ ] Sensitive data accessed
- [ ] Bulk data export
- [ ] Data deletion (soft/hard)
- [ ] Configuration changes

### Anomalies
- [ ] Repeated failed uploads
- [ ] Unusual API call patterns
- [ ] Access from new location/device
- [ ] Privilege escalation attempts

## Database Schema
```sql
-- Migration: Add audit_logs table
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    event_type VARCHAR(100) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    username VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    resource_type VARCHAR(100),
    resource_id INTEGER,
    attempted_action VARCHAR(100),
    metadata JSONB,
    severity VARCHAR(20) DEFAULT 'info',

    INDEX idx_audit_timestamp (timestamp),
    INDEX idx_audit_user_id (user_id),
    INDEX idx_audit_event_type (event_type),
    INDEX idx_audit_severity (severity)
);
```

## Acceptance Criteria
- [ ] All authentication endpoints log success/failure
- [ ] All permission checks log denials
- [ ] Repeated failures tracked and alerted
- [ ] Suspicious patterns detected and logged
- [ ] Audit logs include:
  - User ID and username
  - Timestamp (UTC)
  - IP address and user agent
  - Resource type and ID
  - Action attempted
  - Contextual metadata
- [ ] `SECURITY.md` updated with:
  - What is logged
  - Log retention policy
  - How to review audit logs
  - Incident response procedures
- [ ] Log rotation configured (prevent disk fill)
- [ ] Sensitive data (passwords, tokens) never logged

## Testing Plan
1. Review all endpoints in `app/routes/`
2. Identify security-relevant actions
3. Add logging calls with appropriate context
4. Test each logged event
5. Verify log format and content
6. Test suspicious activity detection
7. Document log analysis procedures

## Documentation Updates
- [ ] Update `SECURITY.md` with audit logging section:
  ```markdown
  ## Audit Logging

  ### What is Logged
  - Authentication events (login, logout, password reset)
  - Authorization failures (permission denied, unauthorized access)
  - Sensitive data access (PII, confidential documents)
  - Configuration changes (settings, permissions, roles)
  - Anomalous behavior (repeated failures, suspicious patterns)

  ### Log Format
  All audit logs use structured JSON format with fields:
  - `timestamp`: ISO 8601 UTC timestamp
  - `event_type`: Categorized event type (e.g., "auth.login.failed")
  - `user_id`: Authenticated user ID (if available)
  - `username`: User email/username
  - `ip_address`: Client IP address
  - `user_agent`: Client user agent string
  - `resource_type` and `resource_id`: Affected resource
  - `attempted_action`: Action user tried to perform
  - `metadata`: Additional context (JSON object)
  - `severity`: info, warning, error, critical

  ### Reviewing Audit Logs
  Logs are stored in:
  - **Database**: `audit_logs` table for queryable history
  - **Files**: `/var/log/surfsense/audit.log` (structured JSON)

  Query examples:
  ```sql
  -- Failed login attempts in last 24 hours
  SELECT * FROM audit_logs
  WHERE event_type = 'auth.login.failed'
  AND timestamp > NOW() - INTERVAL '24 hours';

  -- Permission denials for specific user
  SELECT * FROM audit_logs
  WHERE event_type = 'authz.permission_denied'
  AND user_id = 123;
  ```

  ### Retention Policy
  - Database logs: 90 days (configurable)
  - File logs: 1 year, rotated daily, compressed after 7 days

  ### Incident Response
  When investigating security incidents:
  1. Identify affected time range and users
  2. Query audit logs for event timeline
  3. Check for related suspicious activity
  4. Correlate with application logs
  5. Document findings in incident report
  ```
- [ ] Add log analysis guide to internal documentation
- [ ] Create Grafana/Kibana dashboard for audit log visualization

## Architecture Impact
- **Medium Impact**: Adds logging calls throughout codebase
- **Performance**: Minimal (async logging, < 1ms per event)
- **Storage**: ~100MB/month for typical usage (configurable retention)
- **Security**: Enhances security posture significantly

## Related Issues/PRs
- Addresses continuous improvement recommendation #3
- Complements existing security hardening efforts
- Enables SOC 2 / compliance requirements

## Priority
**Medium-High** - Essential for compliance and incident response

## Effort Estimate
- **Audit log infrastructure**: 6-8 hours
- **Authentication logging**: 4-6 hours
- **Authorization logging**: 6-8 hours
- **Anomaly detection**: 8-10 hours
- **Documentation**: 4-6 hours
- **Testing & Verification**: 6-8 hours
- **Total**: 2-3 weeks

## References
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [CIS Critical Security Controls: Audit Log Management](https://www.cisecurity.org/)
- [Python Logging Best Practices](https://docs.python.org/3/howto/logging.html)
- [Baseline audit logging exists for sharing and failed writes](/)
