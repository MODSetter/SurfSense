# Google Drive OAuth Testing Guide

## Quick Setup for Testing & Screen Recording

### 1. Environment Setup

**Frontend (.env.local in surfsense_web/):**
```bash
NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE=GOOGLE
NEXT_PUBLIC_ETL_SERVICE=DOCLING
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_actual_google_client_id_here
```

**Backend (.env in surfsense_backend/):**
```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/surfsense
SECRET_KEY=your_secret_key_here
NEXT_FRONTEND_URL=http://localhost:3000
AUTH_TYPE=GOOGLE
GOOGLE_OAUTH_CLIENT_ID=your_actual_google_client_id_here
GOOGLE_OAUTH_CLIENT_SECRET=your_actual_google_client_secret_here
EMBEDDING_MODEL=mixedbread-ai/mxbai-embed-large-v1
ETL_SERVICE=DOCLING
```

### 2. Google Cloud Console Setup (if not done)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create/select a project
3. Enable Google Drive API
4. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:3000/auth/google/callback`
5. Copy Client ID and Client Secret to your .env files

### 3. Start Development Servers

**Terminal 1 - Backend:**
```bash
cd surfsense_backend
# Install dependencies if needed
pip install -r requirements.txt
# Start backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd surfsense_web
# Install dependencies if needed
npm install --legacy-peer-deps
# Start frontend
npm run dev
```

### 4. Testing the OAuth Flow

1. **Navigate to Google Drive Connector:**
   - Open: `http://localhost:3000`
   - Login (if auth is required)
   - Go to: Dashboard → Connectors → Add Connector → Google Drive

2. **Test OAuth Flow:**
   - Enter connector name
   - Click "Connect to Google Drive"
   - Should redirect to Google OAuth
   - Authorize the application
   - Should redirect back with file list
   - Select files and create connector

### 5. OAuth Flow URLs (for debugging)

- **OAuth Initiation:** Frontend generates Google OAuth URL
- **OAuth Callback:** `http://localhost:3000/auth/google/callback`
- **Session API:** `http://localhost:3000/api/auth/google/session`
- **Files API:** `http://localhost:3000/api/google-drive/files`

### 6. Screen Recording Checklist

✅ **Before Recording:**
- [ ] Both servers running (backend on :8000, frontend on :3000)
- [ ] Google OAuth credentials configured
- [ ] Can access the Google Drive connector page
- [ ] Test OAuth flow once to ensure it works

✅ **During Recording:**
- [ ] Show the connector setup page
- [ ] Demonstrate OAuth flow
- [ ] Show file selection interface
- [ ] Create the connector successfully

### 7. Troubleshooting

**"Google Client ID not configured" error:**
- Check `NEXT_PUBLIC_GOOGLE_CLIENT_ID` in frontend .env.local

**"Failed to exchange authorization code" error:**
- Check `GOOGLE_OAUTH_CLIENT_SECRET` in backend .env
- Verify redirect URI in Google Cloud Console

**"Failed to fetch Google Drive files" error:**
- Should be fixed with new architecture
- Check browser network tab for API call details

### 8. Demo Script

1. "Here's the Google Drive connector setup page"
2. "I'll enter a connector name and click Connect to Google Drive"
3. "This redirects to Google's OAuth page"
4. "After authorization, we're back with a list of Google Drive files"
5. "I can select which files to index"
6. "And create the connector successfully"

The OAuth flow should now work properly with the restructured implementation!