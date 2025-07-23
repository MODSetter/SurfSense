import logging
from typing import List, Optional, Dict, Any
import time

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    raise ImportError("Please install required dependencies: pip install requests")

logger = logging.getLogger(__name__)

# Google Drive API configuration
DRIVE_API_BASE_URL = "https://www.googleapis.com/drive/v3"
DRIVE_EXPORT_URL = "https://www.googleapis.com/drive/v3/files/{file_id}/export"
DRIVE_DOWNLOAD_URL = "https://www.googleapis.com/drive/v3/files/{file_id}"

# Supported Google Workspace file types for export
GOOGLE_WORKSPACE_EXPORT_FORMATS = {
    'application/vnd.google-apps.document': 'text/plain',  # Google Docs to plain text
    'application/vnd.google-apps.spreadsheet': 'text/csv',  # Google Sheets to CSV
    'application/vnd.google-apps.presentation': 'text/plain',  # Google Slides to plain text
    'application/vnd.google-apps.form': 'text/plain',  # Google Forms to plain text
}

# Supported direct download file types
SUPPORTED_FILE_TYPES = {
    'text/plain', 'text/csv', 'text/html', 'text/markdown',
    'application/pdf', 'application/json', 'application/xml',
    'text/xml', 'application/rtf'
}

# Maximum file size in bytes (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

class GoogleDriveConnector:
    """Connector for interacting with the Google Drive API."""

    def __init__(self, access_token: str, refresh_token: str):
        """
        Initializes the Google Drive connector.

        Args:
            access_token: Google OAuth2 access token.
            refresh_token: Google OAuth2 refresh token for token renewal.
        """
        if not access_token:
            raise ValueError("Google Drive access token cannot be empty.")
        if not refresh_token:
            raise ValueError("Google Drive refresh token cannot be empty.")
        
        self.access_token = access_token
        self.refresh_token = refresh_token
        
        # Configure session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],  # Updated for urllib3 v2
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _make_authenticated_request(self, url: str, params: Optional[Dict] = None, stream: bool = False) -> Optional[requests.Response]:
        """
        Makes an authenticated request to the Google Drive API with automatic token refresh.

        Args:
            url: The API endpoint URL.
            params: Query parameters for the request.
            stream: Whether to stream the response.

        Returns:
            The response object or None if the request fails.
        """
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json'
        }
        
        try:
            response = self.session.get(url, headers=headers, params=params, stream=stream, timeout=30)
            
            # Handle rate limiting with exponential backoff
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 1))
                logger.warning(f"Rate limited. Retrying after {retry_after} seconds.")
                time.sleep(retry_after)
                return self._make_authenticated_request(url, params, stream)
            
            # Handle token expiration (would need OAuth refresh logic here)
            if response.status_code == 401:
                logger.error("Access token expired. Token refresh needed.")
                return None
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None

    def list_files(self, folder_id: Optional[str] = None, page_size: int = 1000) -> List[Dict[str, Any]]:
        """
        Lists files from Google Drive.

        Args:
            folder_id: Optional folder ID to list files from. If None, lists from root.
            page_size: Number of files to retrieve per request.

        Returns:
            A list of dictionaries containing file metadata.
        """
        files_list = []
        
        # Build query string
        query_parts = ["trashed=false"]
        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")
        
        params = {
            'q': ' and '.join(query_parts),
            'pageSize': page_size,
            'fields': 'nextPageToken,files(id,name,mimeType,size,modifiedTime,parents,webViewLink,createdTime)'
        }
        
        try:
            while True:
                response = self._make_authenticated_request(f"{DRIVE_API_BASE_URL}/files", params=params)
                if not response:
                    break
                
                data = response.json()
                files_list.extend(data.get('files', []))
                
                # Check for next page
                next_page_token = data.get('nextPageToken')
                if not next_page_token:
                    break
                params['pageToken'] = next_page_token
                
            logger.info(f"Retrieved {len(files_list)} files from Google Drive.")
            return files_list
            
        except Exception as e:
            logger.error(f"Failed to list Google Drive files: {e}")
            return []

    def get_file_content(self, file_id: str, mime_type: str) -> Optional[str]:
        """
        Retrieves the content of a file from Google Drive.

        Args:
            file_id: The ID of the file to retrieve.
            mime_type: The MIME type of the file.

        Returns:
            The file content as a string, or None if retrieval fails.
        """
        try:
            # Check if it's a Google Workspace file that needs export
            if mime_type in GOOGLE_WORKSPACE_EXPORT_FORMATS:
                export_mime_type = GOOGLE_WORKSPACE_EXPORT_FORMATS[mime_type]
                url = DRIVE_EXPORT_URL.format(file_id=file_id)
                params = {'mimeType': export_mime_type}
            elif mime_type in SUPPORTED_FILE_TYPES:
                url = DRIVE_DOWNLOAD_URL.format(file_id=file_id)
                params = {'alt': 'media'}
            else:
                logger.warning(f"Unsupported file type: {mime_type}")
                return None

            response = self._make_authenticated_request(url, params=params, stream=True)
            if not response:
                return None

            # Check file size before downloading
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > MAX_FILE_SIZE:
                logger.warning(f"File {file_id} exceeds max size limit. Skipping.")
                return None

            # Read content with size limit
            content = ""
            total_size = 0
            for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
                if chunk:
                    total_size += len(chunk.encode('utf-8'))
                    if total_size > MAX_FILE_SIZE:
                        logger.warning(f"File {file_id} content exceeds max size during download. Truncating.")
                        break
                    content += chunk

            return content

        except UnicodeDecodeError:
            logger.warning(f"Could not decode file {file_id} as UTF-8. Skipping.")
            return None
        except Exception as e:
            logger.error(f"Failed to get content for file {file_id}: {e}")
            return None

    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves metadata for a specific file.

        Args:
            file_id: The ID of the file.

        Returns:
            A dictionary containing file metadata, or None if retrieval fails.
        """
        params = {
            'fields': 'id,name,mimeType,size,modifiedTime,createdTime,parents,webViewLink,description'
        }
        
        response = self._make_authenticated_request(f"{DRIVE_API_BASE_URL}/files/{file_id}", params=params)
        if not response:
            return None
        
        try:
            return response.json()
        except Exception as e:
            logger.error(f"Failed to parse metadata for file {file_id}: {e}")
            return None

    def search_files(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Searches for files in Google Drive.

        Args:
            query: The search query.
            max_results: Maximum number of results to return.

        Returns:
            A list of dictionaries containing file metadata.
        """
        params = {
            'q': f"trashed=false and fullText contains '{query}'",
            'pageSize': min(max_results, 1000),
            'fields': 'files(id,name,mimeType,size,modifiedTime,parents,webViewLink)'
        }
        
        response = self._make_authenticated_request(f"{DRIVE_API_BASE_URL}/files", params=params)
        if not response:
            return []
        
        try:
            data = response.json()
            return data.get('files', [])
        except Exception as e:
            logger.error(f"Failed to search Google Drive files: {e}")
            return []

    def get_folder_structure(self, folder_id: Optional[str] = None, max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
        """
        Retrieves the folder structure from Google Drive.

        Args:
            folder_id: The folder ID to start from. If None, starts from root.
            max_depth: Maximum depth to traverse.
            current_depth: Current traversal depth.

        Returns:
            A nested dictionary representing the folder structure.
        """
        if current_depth >= max_depth:
            return {}

        # Get folders in current directory
        query_parts = ["trashed=false", "mimeType='application/vnd.google-apps.folder'"]
        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")

        params = {
            'q': ' and '.join(query_parts),
            'fields': 'files(id,name,parents)',
            'pageSize': 1000
        }

        response = self._make_authenticated_request(f"{DRIVE_API_BASE_URL}/files", params=params)
        if not response:
            return {}

        try:
            data = response.json()
            folders = data.get('files', [])
            
            structure = {}
            for folder in folders:
                folder_name = folder['name']
                folder_id = folder['id']
                
                # Recursively get subfolder structure
                subfolders = self.get_folder_structure(folder_id, max_depth, current_depth + 1)
                structure[folder_name] = {
                    'id': folder_id,
                    'subfolders': subfolders
                }
            
            return structure
            
        except Exception as e:
            logger.error(f"Failed to get folder structure: {e}")
            return {}