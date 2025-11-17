# Social Media Links Management

This document explains how to manage dynamic social media links for the SurfSense homepage footer.

## Overview

Social media links are now managed dynamically through the backend API. No hardcoded links exist in the frontend code. Administrators can add, edit, or remove links, and they will automatically appear or disappear from the homepage footer.

## API Endpoints

All admin endpoints require authentication and **superuser** privileges.

### Base URL
```
{BACKEND_URL}/api/v1/social-media-links
```

### 1. Get All Links (Admin)
```bash
GET /api/v1/social-media-links
Authorization: Bearer {your_jwt_token}
```

**Response:**
```json
[
  {
    "id": 1,
    "platform": "MASTODON",
    "url": "https://mastodon.social/@username",
    "label": "Follow us on Mastodon",
    "display_order": 0,
    "is_active": true,
    "created_at": "2025-11-17T00:00:00Z"
  }
]
```

### 2. Get Public Links (No Auth Required)
```bash
GET /api/v1/social-media-links/public
```

This endpoint returns only active links, ordered by `display_order`. Used by the homepage footer.

### 3. Create a Link (Admin)
```bash
POST /api/v1/social-media-links
Authorization: Bearer {your_jwt_token}
Content-Type: application/json

{
  "platform": "MASTODON",
  "url": "https://mastodon.social/@username",
  "label": "Mastodon",
  "display_order": 0,
  "is_active": true
}
```

**Supported Platforms:**
- `MASTODON`
- `PIXELFED`
- `BOOKWYRM`
- `LEMMY`
- `PEERTUBE`
- `GITHUB`
- `GITLAB`
- `MATRIX`
- `LINKEDIN`
- `WEBSITE`
- `EMAIL`
- `OTHER`

### 4. Update a Link (Admin)
```bash
PATCH /api/v1/social-media-links/{link_id}
Authorization: Bearer {your_jwt_token}
Content-Type: application/json

{
  "url": "https://new-url.example.com",
  "is_active": false
}
```

You can update any field(s). Omit fields you don't want to change.

### 5. Delete a Link (Admin)
```bash
DELETE /api/v1/social-media-links/{link_id}
Authorization: Bearer {your_jwt_token}
```

## Example: Using cURL

### Add a Mastodon Link
```bash
# First, login to get JWT token
TOKEN=$(curl -X POST "http://localhost:8000/auth/jwt/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=yourpassword" \
  | jq -r '.access_token')

# Create the link
curl -X POST "http://localhost:8000/api/v1/social-media-links" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "MASTODON",
    "url": "https://mastodon.social/@surfsense",
    "label": "Mastodon",
    "display_order": 1,
    "is_active": true
  }'
```

### Add Multiple Links
```bash
# Pixelfed
curl -X POST "http://localhost:8000/api/v1/social-media-links" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "PIXELFED",
    "url": "https://pixelfed.social/username",
    "label": "Pixelfed",
    "display_order": 2,
    "is_active": true
  }'

# Bookwyrm
curl -X POST "http://localhost:8000/api/v1/social-media-links" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "BOOKWYRM",
    "url": "https://bookwyrm.social/user/username",
    "label": "Bookwyrm",
    "display_order": 3,
    "is_active": true
  }'
```

### Update a Link
```bash
# Hide a link without deleting it
curl -X PATCH "http://localhost:8000/api/v1/social-media-links/1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

### List All Links
```bash
curl "http://localhost:8000/api/v1/social-media-links" \
  -H "Authorization: Bearer $TOKEN"
```

### Delete a Link
```bash
curl -X DELETE "http://localhost:8000/api/v1/social-media-links/1" \
  -H "Authorization: Bearer $TOKEN"
```

## Icon Mapping

The frontend automatically maps platform names to appropriate icons:

| Platform | Icon |
|----------|------|
| MASTODON | Mastodon logo |
| PIXELFED | Photo icon |
| BOOKWYRM | Book icon |
| GITHUB | GitHub logo |
| GITLAB | GitLab logo |
| LINKEDIN | LinkedIn logo |
| WEBSITE | World/globe icon |
| EMAIL | Mail icon |
| MATRIX | Matrix logo |
| PEERTUBE | TV/video icon |
| LEMMY | World icon |
| OTHER | World icon |

## How It Works

1. **Backend:** Social media links are stored in the `social_media_links` database table
2. **Public API:** The `/api/v1/social-media-links/public` endpoint returns only active links
3. **Frontend:** The footer component (`components/homepage/footer.tsx`) fetches links on page load
4. **Display:** Only links with `is_active=true` are shown, ordered by `display_order`
5. **Icons:** Platform-specific icons are automatically selected based on the `platform` field

## Database Migration

To apply the database schema:

```bash
cd surfsense_backend
alembic upgrade head
```

This will create the `social_media_links` table and the `socialmediaplatform` enum type.

## Security Notes

- **Admin endpoints require superuser privileges** - regular users cannot manage links
- **Public endpoint is unauthenticated** - anyone can view active links (as intended for homepage display)
- **No hardcoded URLs** - all social media links come from the database
- **Validation** - URLs are validated (max 500 chars), labels max 100 chars

## Future Enhancements

Future improvements could include:

1. **Web UI:** A graphical admin panel in the dashboard for managing links
2. **Drag-and-drop reordering:** UI to easily reorder links by changing `display_order`
3. **Link analytics:** Track clicks on social media links
4. **Per-user links:** Allow different users to have different social links (currently global)
5. **Link preview:** Show how the footer will look before saving changes

## Troubleshooting

**Links not appearing on homepage:**
1. Check that `is_active=true` for the link
2. Verify the backend API is reachable from frontend
3. Check browser console for fetch errors
4. Confirm `NEXT_PUBLIC_FASTAPI_BACKEND_URL` environment variable is set correctly

**Cannot create links:**
1. Ensure you're logged in as a superuser
2. Check JWT token is valid and not expired
3. Verify request payload matches the schema

**Icons not displaying:**
1. Check that the platform name exactly matches one of the supported platforms (case-sensitive)
2. Unsupported platforms will default to the world/globe icon
