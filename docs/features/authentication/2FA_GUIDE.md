# Two-Factor Authentication (2FA) Guide

## Overview

This document describes the complete Two-Factor Authentication (2FA) implementation for SurfSense. The implementation includes TOTP-based authentication with QR code setup, backup codes for account recovery, and comprehensive security event logging.

## Features Implemented

### Frontend (Next.js/React)

#### 1. Login Flow with 2FA

**Location:** `surfsense_web/app/(home)/login/LocalLoginForm.tsx`

- Animated 2FA code input field appears after password entry when 2FA is required
- Input field specifications:
  - Type: text with `inputMode="numeric"`
  - Pattern: `[0-9]{6}`
  - MaxLength: 6
  - Auto-focus on appearance
  - Centered text with tracking-widest styling
  - Placeholder: "000000"
  - Autocomplete: "one-time-code"
- "Verify Code" and "Back to Login" buttons for 2FA flow
- Email/password fields disabled when in 2FA verification mode
- State management for 2FA:
  - `requires2FA`: Boolean flag
  - `temporaryToken`: Temporary token from initial login
  - `totpCode`: User-entered TOTP code
  - `isVerifying2FA`: Loading state

#### 2. Security Settings Page

**Location:** `surfsense_web/app/dashboard/security/page.tsx`

- Real-time 2FA status display
- Enable/Disable 2FA functionality
- QR code display for authenticator app setup
- Manual secret key entry option
- Backup codes management and download
- Responsive UI with proper error handling

#### 3. Authentication Service Updates

**Location:** `surfsense_web/lib/apis/auth-api.service.ts`

- Changed login endpoint from `/auth/jwt/login` to `/api/v1/auth/2fa/login`
- Added `verify2FA()` method to handle 2FA verification
- Updated type definitions in `auth.types.ts`:
  - `LoginResponse` includes `requires_2fa` and `temporary_token`
  - New `Verify2FARequest` and `Verify2FAResponse` types

#### 4. No-Auth Endpoints Configuration

**Location:** `surfsense_web/lib/apis/base-api.service.ts`

Added to noAuthEndpoints array:
- `/api/v1/auth/2fa/login`
- `/api/v1/auth/2fa/verify`

#### 5. Internationalization (i18n)

**Location:** `surfsense_web/messages/en.json`

Complete English translations added for:
- Titles and descriptions
- Button labels
- Error messages
- Success messages

### Backend (FastAPI/Python)

#### 1. Database Models

**Location:** `surfsense_backend/app/db.py`

- `SecurityEventType` enum: Defines all security event types
- `SecurityEvent` model: Audit log for security events
- User model extensions:
  - `two_fa_enabled`: Boolean field
  - `totp_secret`: Encrypted secret storage
  - `backup_codes`: JSON array of hashed backup codes

#### 2. Database Migration

**Location:** `surfsense_backend/alembic/versions/42_add_security_events_table.py`

- Creates `security_events` table
- Adds indexes for efficient querying
- Includes event type, user ID, IP address, user agent, success status, and details

To apply migration:
```bash
cd surfsense_backend
alembic upgrade head
```

#### 3. Security Event Service

**Location:** `surfsense_backend/app/services/security_event_service.py`

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

#### 4. 2FA Routes

**Location:** `surfsense_backend/app/routes/two_fa_routes.py`

Enhanced with security event logging, captures IP address and user agent from requests.

**Endpoints:**
- `GET /auth/2fa/status` - Get user's 2FA status
- `POST /auth/2fa/setup` - Initialize 2FA setup
- `POST /auth/2fa/verify-setup` - Verify and enable 2FA
- `POST /auth/2fa/disable` - Disable 2FA
- `POST /auth/2fa/backup-codes` - Regenerate backup codes
- `POST /auth/2fa/login` - Login with password (returns temp token if 2FA enabled)
- `POST /auth/2fa/verify` - Verify 2FA code and complete login

## User Workflows

### Enable 2FA

1. User navigates to Security Settings
2. Click "Enable 2FA" button
3. QR code displays with manual entry key option
4. Scan QR code with authenticator app (Google Authenticator, Authy, etc.)
5. Enter 6-digit verification code
6. Receive 10 backup codes
7. Download backup codes for safe storage
8. 2FA status shows "enabled"

### Login with 2FA

1. User enters email and password
2. System validates credentials
3. If 2FA enabled, 2FA code input appears
4. Enter TOTP code from authenticator app (or backup code)
5. System verifies code
6. Successfully logged in

### Login with Backup Code

1. User enters email and password
2. 2FA code input appears
3. Enter one of the backup codes instead of TOTP
4. Successfully logged in
5. Backup code is marked as used and removed

### Disable 2FA

1. Navigate to Security Settings
2. Click "Disable 2FA" button
3. Enter TOTP code or backup code for verification
4. 2FA successfully disabled
5. Status shows "disabled"

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
- Temporary tokens expire after 5 minutes
- Tokens stored in Redis with TTL

### Account Recovery

- 10 single-use backup codes generated on 2FA enable
- Backup codes can be regenerated (requires TOTP verification)
- Codes can be downloaded as a text file
- Used codes are automatically removed

### Session Security

Fixed issue where Site Settings page was logging out users:
- Added `credentials: "include"` to all authenticated fetch requests
- Added proper headers including Content-Type
- Applied to both `/verify-token` and `/api/v1/site-config` endpoints
- Ensures cookies/session data are sent with cross-origin requests

**Files affected:**
- `surfsense_web/app/dashboard/site-settings/page.tsx`
- `surfsense_web/contexts/SiteConfigContext.tsx`

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

### Login with Password

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

## Testing Checklist

### Enable 2FA Flow
- [ ] Navigate to Security Settings
- [ ] Click "Enable 2FA" button
- [ ] QR code displays correctly
- [ ] Manual entry key is visible and can be copied
- [ ] Scan QR code with authenticator app
- [ ] Enter 6-digit code from app
- [ ] Receive 10 backup codes
- [ ] Download backup codes
- [ ] Verify 2FA status shows "enabled"

### Login with 2FA
- [ ] Log out of application
- [ ] Enter email and password
- [ ] Prompted for 2FA code
- [ ] Enter TOTP code from authenticator app
- [ ] Successfully logged in
- [ ] Security event logged

### Login with Backup Code
- [ ] Log out of application
- [ ] Enter email and password
- [ ] Prompted for 2FA code
- [ ] Enter one of the backup codes
- [ ] Successfully logged in
- [ ] Verify backup code is marked as used
- [ ] Security events logged (login + backup code usage)

### Disable 2FA
- [ ] Navigate to Security Settings
- [ ] Click "Disable 2FA" button
- [ ] Enter TOTP code or backup code
- [ ] 2FA successfully disabled
- [ ] Verify 2FA status shows "disabled"
- [ ] Security event logged

### Error Handling
- [ ] Test invalid TOTP code (should show error)
- [ ] Test expired temporary login token
- [ ] Test enabling 2FA when already enabled
- [ ] Test disabling 2FA when not enabled
- [ ] Test using same backup code twice

### Security Event Logging
- [ ] Check database for security_events entries
- [ ] Verify IP addresses are captured
- [ ] Verify user agents are captured
- [ ] Verify no sensitive data (TOTP codes) in logs
- [ ] Verify all event types are logged correctly

### Site Settings Access
- [ ] Can access Site Settings without logout
- [ ] Site configuration loads correctly
- [ ] Can save configuration changes
- [ ] No authentication errors in console

## Environment Requirements

- Backend must have Redis running (for temporary 2FA tokens)
- `CELERY_BROKER_URL` environment variable must be set
- `CORS_ORIGINS` must include the frontend URL
- `NEXT_PUBLIC_FASTAPI_BACKEND_URL` must be set on frontend

## Files Modified/Created

### Backend

**Created:**
- `surfsense_backend/app/services/security_event_service.py`
- `surfsense_backend/alembic/versions/42_add_security_events_table.py`

**Modified:**
- `surfsense_backend/app/db.py` - Added SecurityEventType enum and SecurityEvent model
- `surfsense_backend/app/routes/two_fa_routes.py` - Added security event logging

### Frontend

**Modified:**
- `surfsense_web/contracts/types/auth.types.ts` - Added 2FA type definitions
- `surfsense_web/lib/apis/auth-api.service.ts` - Updated authentication service
- `surfsense_web/lib/apis/base-api.service.ts` - Added no-auth endpoints
- `surfsense_web/app/(home)/login/LocalLoginForm.tsx` - Implemented 2FA flow
- `surfsense_web/app/dashboard/site-settings/page.tsx` - Fixed credential handling
- `surfsense_web/contexts/SiteConfigContext.tsx` - Fixed credential handling
- `surfsense_web/app/dashboard/security/page.tsx` - Updated with functional 2FA UI
- `surfsense_web/messages/en.json` - Added 2FA translations

## Rate Limiting

### Current Implementation

Rate limiting is implemented using slowapi library:
- 2FA verification attempts limited to prevent brute force attacks
- Rate limits applied per IP address
- Backend returns appropriate error messages when limits exceeded

### Future Enhancements

Frontend visualization:
- Display remaining attempts
- Show lockout timer
- Disable form during lockout
- Clear visual feedback for users

## Future Enhancements

### Additional Languages
- Add Latvian translations to `messages/lv.json`
- Add translations for other supported languages

### Enhanced Security
- CAPTCHA for repeated failed attempts
- Email notifications for security events
- Device fingerprinting
- Trusted device management

### Admin Dashboard
- View security events for all users
- Force 2FA for specific users or roles
- Security analytics and reporting

### Account Recovery Options
- SMS-based backup codes
- Recovery email option
- Admin-assisted recovery flow

## Troubleshooting

### User Getting Logged Out

If users are being logged out when accessing certain pages:

1. Check that all authenticated fetch requests include `credentials: "include"`
2. Verify proper headers are set (Content-Type, Authorization)
3. Check CORS configuration in backend allows credentials
4. Verify frontend URL matches CORS_ORIGINS setting

### 2FA Code Not Accepted

1. Check time synchronization on server and user's device
2. Verify QR code was scanned correctly
3. Try manual entry of secret key
4. Check security events table for failure reasons
5. Verify Redis is running and accessible

### Backup Codes Not Working

1. Check if backup code has already been used
2. Verify backup codes are stored correctly in database
3. Check bcrypt hashing is working properly
4. Review security events for details

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

---

**Last Updated:** November 29, 2025
