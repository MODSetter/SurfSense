# Two-Factor Authentication (2FA) Implementation

## Overview

This document describes the Two-Factor Authentication (2FA) implementation for SurfSense. The implementation includes TOTP-based authentication with QR code setup, backup codes for account recovery, and comprehensive security event logging.

## Features Implemented

### Frontend (Next.js/React)

1. **Security Settings Page** (`surfsense_web/app/dashboard/security/page.tsx`)
   - Real-time 2FA status display
   - Enable/Disable 2FA functionality
   - QR code display for authenticator app setup
   - Manual secret key entry option
   - Backup codes management
   - Responsive UI with proper error handling

2. **User Flows**
   - **Enable 2FA**: User clicks "Enable 2FA" → Scans QR code → Enters verification code → Receives backup codes
   - **Login with 2FA**: User enters password → Enters TOTP code or backup code → Successfully logged in
   - **Disable 2FA**: User clicks "Disable 2FA" → Enters TOTP or backup code → 2FA disabled
   - **Backup Codes**: Download backup codes for offline storage

3. **Internationalization (i18n)**
   - Complete English translations added to `surfsense_web/messages/en.json`
   - All user-facing messages are translatable
   - Translations include: titles, descriptions, button labels, error messages, success messages

### Backend (FastAPI/Python)

1. **Database Models** (`surfsense_backend/app/db.py`)
   - `SecurityEventType` enum: Defines all security event types
   - `SecurityEvent` model: Audit log for security events
   - User model extensions: `two_fa_enabled`, `totp_secret`, `backup_codes`

2. **Migration** (`surfsense_backend/alembic/versions/42_add_security_events_table.py`)
   - Creates `security_events` table
   - Adds indexes for efficient querying
   - Includes event type, user ID, IP address, user agent, success status, and details

3. **Security Event Service** (`surfsense_backend/app/services/security_event_service.py`)
   - Centralized service for logging security events
   - Logs IP address and user agent for each event
   - Never logs sensitive information (TOTP codes or secrets)
   - Event types logged:
     - 2FA setup initiated
     - 2FA enabled/disabled
     - 2FA verification success/failure
     - 2FA login success/failure
     - Backup code used
     - Backup codes regenerated
     - Password login success/failure

4. **2FA Routes** (`surfsense_backend/app/routes/two_fa_routes.py`)
   - Enhanced with security event logging
   - Captures IP address and user agent from requests
   - Logs all security-critical actions
   - Endpoints:
     - `GET /auth/2fa/status` - Get user's 2FA status
     - `POST /auth/2fa/setup` - Initialize 2FA setup
     - `POST /auth/2fa/verify-setup` - Verify and enable 2FA
     - `POST /auth/2fa/disable` - Disable 2FA
     - `POST /auth/2fa/backup-codes` - Regenerate backup codes
     - `POST /auth/2fa/login` - Login with password (returns temp token if 2FA enabled)
     - `POST /auth/2fa/verify` - Verify 2FA code and complete login

## Security Features

### Event Logging

All 2FA-related actions are logged to the `security_events` table with:
- Event type (enum)
- User ID
- IP address
- User agent
- Success/failure status
- Timestamp (automatic)
- Additional details (JSON)

### Data Protection

- TOTP secrets are stored encrypted
- Backup codes are hashed using bcrypt
- No sensitive data is logged
- Automatic cleanup of used backup codes

### Account Recovery

- 10 single-use backup codes generated on 2FA enable
- Backup codes can be regenerated (requires TOTP verification)
- Codes can be downloaded as a text file
- Used codes are automatically removed

## Testing Checklist

### 1. Enable 2FA Flow
- [ ] Navigate to Security Settings
- [ ] Click "Enable 2FA" button
- [ ] QR code displays correctly
- [ ] Manual entry key is visible and can be copied
- [ ] Scan QR code with authenticator app (Google Authenticator, Authy, etc.)
- [ ] Enter 6-digit code from app
- [ ] Receive 10 backup codes
- [ ] Download backup codes
- [ ] Verify 2FA status shows "enabled"

### 2. Login with 2FA
- [ ] Log out of application
- [ ] Enter email and password
- [ ] Prompted for 2FA code
- [ ] Enter TOTP code from authenticator app
- [ ] Successfully logged in
- [ ] Security event logged

### 3. Login with Backup Code
- [ ] Log out of application
- [ ] Enter email and password
- [ ] Prompted for 2FA code
- [ ] Enter one of the backup codes
- [ ] Successfully logged in
- [ ] Verify backup code is marked as used
- [ ] Security events logged (login + backup code usage)

### 4. Disable 2FA
- [ ] Navigate to Security Settings
- [ ] Click "Disable 2FA" button
- [ ] Enter TOTP code or backup code
- [ ] 2FA successfully disabled
- [ ] Verify 2FA status shows "disabled"
- [ ] Security event logged

### 5. Error Handling
- [ ] Test invalid TOTP code (should show error)
- [ ] Test expired temporary login token
- [ ] Test enabling 2FA when already enabled
- [ ] Test disabling 2FA when not enabled
- [ ] Test using same backup code twice

### 6. Security Event Logging
- [ ] Check database for security_events entries
- [ ] Verify IP addresses are captured
- [ ] Verify user agents are captured
- [ ] Verify no sensitive data (TOTP codes) in logs
- [ ] Verify all event types are logged correctly

## Database Migration

To apply the security events table migration:

```bash
cd surfsense_backend
alembic upgrade head
```

## Rate Limiting (To Be Implemented)

### Recommended Implementation

While not yet implemented in this iteration, rate limiting should be added:

1. **Backend Rate Limiting**
   - Use `slowapi` or similar library
   - Limit 2FA verification attempts (e.g., 5 attempts per 15 minutes)
   - Lock accounts after excessive failures
   - Return attempt count and lockout time in API responses

2. **Frontend Visualization**
   - Display remaining attempts
   - Show lockout timer
   - Disable form during lockout
   - Clear visual feedback for users

### Placeholder for Rate Limiting

In `surfsense_backend/app/routes/two_fa_routes.py`, add:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/verify")
@limiter.limit("5/15minutes")
async def verify_2fa_login(...):
    # Existing code
```

## API Documentation

### Setup 2FA

**POST** `/auth/2fa/setup`

Requires: Authentication

Response:
```json
{
  "secret": "BASE32_SECRET",
  "qr_code": "base64_encoded_png",
  "uri": "otpauth://totp/..."
}
```

### Verify Setup

**POST** `/auth/2fa/verify-setup`

Requires: Authentication

Request:
```json
{
  "code": "123456"
}
```

Response:
```json
{
  "success": true,
  "backup_codes": ["XXXX-XXXX", "YYYY-YYYY", ...]
}
```

### Get Status

**GET** `/auth/2fa/status`

Requires: Authentication

Response:
```json
{
  "enabled": true,
  "has_backup_codes": true
}
```

### Disable 2FA

**POST** `/auth/2fa/disable`

Requires: Authentication

Request:
```json
{
  "code": "123456"  // TOTP or backup code
}
```

Response:
```json
{
  "success": true,
  "message": "2FA has been disabled."
}
```

### Login with 2FA

**POST** `/auth/2fa/login`

Request:
```json
{
  "username": "user@example.com",
  "password": "password123"
}
```

Response (2FA enabled):
```json
{
  "requires_2fa": true,
  "temporary_token": "temp_token_string"
}
```

Response (2FA disabled):
```json
{
  "access_token": "jwt_token",
  "token_type": "bearer",
  "requires_2fa": false
}
```

### Verify 2FA Login

**POST** `/auth/2fa/verify`

Request:
```json
{
  "temporary_token": "temp_token_string",
  "code": "123456"  // TOTP or backup code
}
```

Response:
```json
{
  "access_token": "jwt_token",
  "token_type": "bearer"
}
```

## Files Modified/Created

### Backend
- **Created**:
  - `surfsense_backend/app/services/security_event_service.py`
  - `surfsense_backend/alembic/versions/42_add_security_events_table.py`

- **Modified**:
  - `surfsense_backend/app/db.py` (added SecurityEventType enum and SecurityEvent model)
  - `surfsense_backend/app/routes/two_fa_routes.py` (added security event logging)

### Frontend
- **Modified**:
  - `surfsense_web/app/dashboard/security/page.tsx` (updated with functional 2FA UI)
  - `surfsense_web/messages/en.json` (added 2FA translations)

## Future Enhancements

1. **Rate Limiting**
   - Implement backend rate limiting for 2FA verification
   - Add frontend visualization of rate limits
   - Account lockout after too many failed attempts

2. **Additional Languages**
   - Add Latvian translations to `messages/lv.json`
   - Add translations for other supported languages

3. **Enhanced Security**
   - CAPTCHA for repeated failed attempts
   - Email notifications for security events
   - Device fingerprinting
   - Trusted device management

4. **Admin Dashboard**
   - View security events for all users
   - Force 2FA for specific users or roles
   - Security analytics and reporting

5. **Account Recovery**
   - SMS-based backup codes
   - Recovery email option
   - Admin-assisted recovery flow

## Support

For issues or questions regarding 2FA implementation:
1. Check the security events table for logged errors
2. Review application logs for detailed error messages
3. Verify database migration was applied successfully
4. Test with multiple authenticator apps to rule out app-specific issues

## References

- [RFC 6238 - TOTP](https://tools.ietf.org/html/rfc6238)
- [Google Authenticator PAM](https://github.com/google/google-authenticator-libpam)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
