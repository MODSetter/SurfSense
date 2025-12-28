"""
Google Drive Connector Module.

Simple, modular approach to Google Drive indexing.
"""

from .change_tracker import categorize_change, fetch_all_changes, get_start_page_token
from .client import GoogleDriveClient
from .content_extractor import download_and_process_file
from .credentials import get_valid_credentials, validate_credentials
from .folder_manager import get_files_in_folder, list_folder_contents

__all__ = [
    "GoogleDriveClient",
    "get_valid_credentials",
    "validate_credentials",
    "download_and_process_file",
    "get_files_in_folder",
    "list_folder_contents",
    "get_start_page_token",
    "fetch_all_changes",
    "categorize_change",
]

