# Media Compression Feature

## Overview

SurfSense now supports automatic image and video compression to reduce file sizes and improve upload speeds. Users can configure compression levels and enable/disable automatic compression.

## Features

### Image Compression
- **Supported Formats**: JPEG, PNG, WebP, GIF, BMP, TIFF
- **Compression Levels**:
  - **Low**: 800px max width, 60% quality, WebP format
  - **Medium** (default): 1200px max width, 75% quality, WebP format
  - **High**: 1920px max width, 85% quality, WebP format
  - **None**: No compression, original file

### Video Compression
- **Supported Formats**: MP4, MOV, AVI, WebM, MKV, FLV, WMV
- **Compression Levels**:
  - **Low**: 480p, 500k bitrate, H.264 codec
  - **Medium** (default): 720p, 1500k bitrate, H.264 codec
  - **High**: 1080p, 3000k bitrate, H.264 codec
  - **None**: No compression, original file

**Note**: Video compression requires FFmpeg to be installed on the server.

## API Endpoints

### Compress Image
```http
POST /api/v1/compress/image
Content-Type: multipart/form-data

file: <image_file>
level: "low" | "medium" | "high" | "none" (optional, defaults to user preference)
```

**Response**:
```json
{
  "success": true,
  "message": "Image compressed successfully (45.2% reduction)",
  "file_path": "/tmp/surfsense/compressed/compressed_abc123.webp",
  "metadata": {
    "original_size": 1024000,
    "compressed_size": 561152,
    "compression_ratio": 45.2,
    "original_format": "JPEG",
    "compressed_format": "webp",
    "original_dimensions": [1920, 1080],
    "compressed_dimensions": [1200, 675]
  }
}
```

### Compress Video
```http
POST /api/v1/compress/video
Content-Type: multipart/form-data

file: <video_file>
level: "low" | "medium" | "high" | "none" (optional, defaults to user preference)
```

**Response**:
```json
{
  "success": true,
  "message": "Video compressed successfully (67.3% reduction)",
  "file_path": "/tmp/surfsense/compressed/compressed_def456.mp4",
  "metadata": {
    "original_size": 51200000,
    "compressed_size": 16742400,
    "compression_ratio": 67.3,
    "original_metadata": {
      "duration": 120.5,
      "width": 1920,
      "height": 1080,
      "video_codec": "h264",
      "video_bitrate": 5000000
    },
    "compressed_metadata": {
      "duration": 120.5,
      "width": 1280,
      "height": 720,
      "video_codec": "h264",
      "video_bitrate": 1500000
    }
  }
}
```

### Get Compression Settings
```http
GET /api/v1/settings
Authorization: Bearer <token>
```

**Response**:
```json
{
  "image_compression_level": "medium",
  "video_compression_level": "medium",
  "auto_compress_enabled": true
}
```

### Update Compression Settings
```http
PUT /api/v1/settings
Authorization: Bearer <token>
Content-Type: application/json

{
  "image_compression_level": "high",
  "video_compression_level": "low",
  "auto_compress_enabled": true
}
```

## Database Schema

Three new columns added to the `user` table:
- `image_compression_level` (VARCHAR(20), default: 'medium')
- `video_compression_level` (VARCHAR(20), default: 'medium')
- `auto_compress_enabled` (BOOLEAN, default: true)

## Implementation Details

### Services

1. **ImageCompressionService** (`app/services/image_compression.py`)
   - Uses Pillow (PIL) for image processing
   - Supports automatic format conversion to WebP for better compression
   - Maintains aspect ratio when resizing
   - Provides compression metadata

2. **VideoCompressionService** (`app/services/video_compression.py`)
   - Uses FFmpeg for video transcoding
   - Supports progress tracking
   - Extracts video metadata
   - Handles multiple codecs and formats

### File Upload Integration

Video file extensions have been added to the allowed extensions list in `documents_routes.py`:
- `.mp4`, `.mov`, `.avi`, `.webm`, `.mkv`, `.flv`, `.wmv`

## Requirements

### Python Packages
```bash
pip install Pillow  # For image compression
pip install pydub   # For audio processing in video compression
```

### System Requirements
```bash
# For video compression
apt-get install ffmpeg

# Verify installation
ffmpeg -version
```

## Usage Examples

### Client-Side (JavaScript)

```javascript
// Upload and compress an image
const compressImage = async (imageFile) => {
  const formData = new FormData();
  formData.append('file', imageFile);
  formData.append('level', 'medium');

  const response = await fetch('/api/v1/compress/image', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });

  const result = await response.json();
  console.log(`Compressed: ${result.metadata.compression_ratio}% reduction`);
  return result;
};

// Update user compression settings
const updateSettings = async (settings) => {
  const response = await fetch('/api/v1/settings', {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(settings)
  });

  return await response.json();
};
```

## Performance Considerations

### Image Compression
- **Processing Time**: ~0.1-0.5 seconds per image (depends on size and level)
- **Memory Usage**: Proportional to image size (typically 10-50MB during processing)
- **Disk Space**: Temporary files are stored in `/tmp/surfsense/compressed/`

### Video Compression
- **Processing Time**: 0.5-2x video duration (depends on level and hardware)
  - Low: ~0.5x duration (faster than realtime)
  - Medium: ~1x duration (about realtime)
  - High: ~2x duration (slower, better quality)
- **Memory Usage**: Moderate (streaming processing)
- **Disk Space**: Temporary files are cleaned up after successful upload

## Cleanup and Maintenance

### Automatic Cleanup
Temporary compressed files should be cleaned up:
1. After successful upload
2. Periodically via cron job

### Recommended Cron Job
```bash
# Clean compressed files older than 24 hours
0 2 * * * find /tmp/surfsense/compressed -type f -mtime +1 -delete
```

## Troubleshooting

### FFmpeg Not Found
**Error**: "FFmpeg is not installed on the server"

**Solution**:
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

### Compression Fails for Large Files
**Issue**: Timeouts or memory errors for very large files

**Solution**:
- Increase file size limits in nginx/application config
- Adjust timeout settings for compression endpoints
- Consider implementing queue-based processing for large files

### Poor Compression Results
**Issue**: File size not significantly reduced

**Possible Causes**:
- File already heavily compressed
- Compression level too high (preserving too much quality)

**Solution**:
- Use lower compression level
- Check original file format (some formats don't compress well)

## Future Enhancements

1. **Queue-based Processing**: Use Celery for background compression of large files
2. **Progress Tracking**: WebSocket-based real-time progress updates
3. **Batch Compression**: Compress multiple files at once
4. **Custom Presets**: Allow users to define custom compression presets
5. **Cloud Storage Integration**: Direct upload to S3/CloudFlare R2 after compression
6. **Compression Analytics**: Track average compression ratios and storage savings
