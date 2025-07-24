# Google Drive Connector Setup Guide

This guide explains how to set up the Google Drive connector for SurfSense, including the OAuth flow implementation.

## Overview

The Google Drive connector allows users to:
- Authenticate with Google Drive using OAuth 2.0
- Browse and select files from their Google Drive
- Index selected files for search within SurfSense

## Implementation Files

### 1. OAuth Callback Handler
**File**: `/surfsense_web/app/auth/google/callback/route.ts`

This API route handles the OAuth callback from Google:
- Exchanges authorization code for access/refresh tokens
- Fetches user's Google Drive files
- Redirects back to the connector page with the data

### 2. Frontend Connector Page
**File**: `/surfsense_web/app/dashboard/[search_space_id]/connectors/add/google-drive-connector/page.tsx`

This React component provides:
- OAuth initiation flow
- File selection interface
- Connector creation

## Required Environment Variables

### Backend (.env in surfsense_backend/)
```bash
# Google OAuth Configuration
GOOGLE_OAUTH_CLIENT_ID=your_google_client_id_here
GOOGLE_OAUTH_CLIENT_SECRET=your_google_client_secret_here
AUTH_TYPE=GOOGLE
```

### Frontend (.env in surfsense_web/)
```bash
# Google OAuth Configuration
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_google_client_id_here
NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8000
```

## Google Cloud Console Setup

1. **Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable Google Drive API**
   - Navigate to APIs & Services > Library
   - Search for "Google Drive API"
   - Click "Enable"

3. **Create OAuth 2.0 Credentials**
   - Go to APIs & Services > Credentials
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Web application"
   - Add authorized redirect URIs:
     - `http://localhost:3000/auth/google/callback` (for development)
     - `https://yourdomain.com/auth/google/callback` (for production)

4. **Configure OAuth Consent Screen**
   - Go to APIs & Services > OAuth consent screen
   - Fill in required information
   - Add scopes: `https://www.googleapis.com/auth/drive.readonly`

## OAuth Flow

1. **User clicks "Connect to Google Drive"**
   - Frontend redirects to Google OAuth authorization URL
   - Includes client_id, redirect_uri, scope, and state parameters

2. **User authorizes on Google**
   - Google redirects to `/auth/google/callback` with authorization code

3. **Backend processes callback**
   - Exchanges authorization code for access/refresh tokens
   - Fetches user's Google Drive files using access token
   - Redirects back to connector page with data

4. **User selects files**
   - Frontend displays list of Google Drive files
   - User selects which files to index

5. **Connector creation**
   - Creates connector with OAuth tokens and selected files
   - Ready for indexing

## Security Considerations

- Uses OAuth 2.0 with PKCE for secure authentication
- Requests only read-only access to Google Drive
- Stores encrypted tokens in the database
- Users can revoke access anytime from Google Account settings

## Troubleshooting

### Common Issues

1. **"Google Client ID not configured" error**
   - Ensure `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is set in frontend .env
   - Verify the client ID is correct

2. **"Failed to exchange authorization code" error**
   - Check `GOOGLE_OAUTH_CLIENT_SECRET` in backend .env
   - Verify redirect URI matches Google Cloud Console settings

3. **"Failed to fetch Google Drive files" error**
   - Ensure Google Drive API is enabled
   - Check OAuth scope includes drive.readonly

### Testing the Implementation

1. Start the development servers
2. Navigate to the Google Drive connector page
3. Click "Connect to Google Drive"
4. Complete OAuth flow
5. Verify files are displayed
6. Create connector with selected files

## File Structure

```
surfsense_web/
├── app/
│   ├── auth/
│   │   └── google/
│   │       └── callback/
│   │           └── route.ts          # OAuth callback handler
│   └── dashboard/
│       └── [search_space_id]/
│           └── connectors/
│               └── add/
│                   └── google-drive-connector/
│                       └── page.tsx   # Frontend connector page
```

## Next Steps

After setting up the Google Drive connector:
1. Configure the required environment variables
2. Set up Google Cloud Console project and credentials
3. Test the OAuth flow in development
4. Deploy with production credentials
5. Monitor connector usage and indexing performance