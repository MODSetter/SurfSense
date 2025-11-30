# Known Limitations

This document outlines known limitations and missing features in the SurfSense platform.

## Email Functionality

### Current Status: Not Implemented

Email sending functionality for password resets and email verification is not currently implemented in the production system.

### Affected Features

- **Password Reset Emails**: Users cannot receive automated password reset links via email
- **Email Verification**: New user email addresses are not verified through automated email workflows

### Workarounds

#### For Users
Contact your system administrator directly for password reset assistance.

#### For Administrators
Manual password resets can be performed using the administrative script:

```bash
cd surfsense_backend
python scripts/update_admin_user.py --email user@example.com --reset-password
```

### Implementation Notes

The codebase contains placeholder TODO comments in the following locations:
- `surfsense_backend/app/users.py`: Password reset token generation
- `surfsense_backend/app/users.py`: Email verification token generation

To implement email functionality in the future:

1. **Add Email Service Dependency**:
   ```toml
   # In pyproject.toml
   "fastapi-mail>=1.4.1",
   ```

2. **Configure SMTP Settings**:
   Add to secrets configuration:
   - SMTP server address
   - SMTP port (typically 587 for TLS)
   - SMTP username
   - SMTP password
   - From email address

3. **Implement Email Service**:
   Create `surfsense_backend/app/services/email_service.py` with methods:
   - `send_password_reset_email(email: str, token: str)`
   - `send_verification_email(email: str, token: str)`

4. **Update User Routes**:
   Replace TODO comments with actual email service calls

### Priority

**Low Priority** - The system functions fully without email support. Users can authenticate via OAuth providers (Google, Airtable) or contact administrators for password assistance.

## Future Considerations

This limitation may be addressed in future releases based on:
- User demand for self-service password reset
- Compliance requirements for email verification
- Availability of SMTP infrastructure

---

**Last Updated**: November 30, 2025
**Status**: Documented, No Immediate Action Required
