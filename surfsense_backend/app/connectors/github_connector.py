import base64
import logging
from typing import List, Optional, Dict, Any
from github3 import login as github_login, exceptions as github_exceptions
from github3.repos.contents import Contents
from github3.exceptions import ForbiddenError, NotFoundError

logger = logging.getLogger(__name__)

# List of common code file extensions to target
CODE_EXTENSIONS = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
    '.cs', '.go', '.rb', '.php', '.swift', '.kt', '.scala', '.rs', '.m',
    '.sh', '.bash', '.ps1', '.lua', '.pl', '.pm', '.r', '.dart', '.sql'
}

# List of common documentation/text file extensions
DOC_EXTENSIONS = {
    '.md', '.txt', '.rst', '.adoc', '.html', '.htm', '.xml', '.json', '.yaml', '.yml', '.toml'
}

# Maximum file size in bytes (e.g., 1MB)
MAX_FILE_SIZE = 1 * 1024 * 1024

class GitHubConnector:
    """Connector for interacting with the GitHub API."""

    # Directories to skip during file traversal
    SKIPPED_DIRS = {
        # Version control
        '.git',
        # Dependencies
        'node_modules',
        'vendor', 
        # Build artifacts / Caches
        'build',
        'dist',
        'target',
        '__pycache__',
        # Virtual environments
        'venv',
        '.venv',
        'env',
        # IDE/Editor config
        '.vscode',
        '.idea',
        '.project',
        '.settings',
        # Temporary / Logs
        'tmp',
        'logs',
        # Add other project-specific irrelevant directories if needed
    }

    def __init__(self, token: str):
        """
        Initializes the GitHub connector.

        Args:
            token: GitHub Personal Access Token (PAT).
        """
        if not token:
            raise ValueError("GitHub token cannot be empty.")
        try:
            self.gh = github_login(token=token)
            # Try a simple authenticated call to check token validity
            self.gh.me()
            logger.info("Successfully authenticated with GitHub API.")
        except (github_exceptions.AuthenticationFailed, ForbiddenError) as e:
            logger.error(f"GitHub authentication failed: {e}")
            raise ValueError("Invalid GitHub token or insufficient permissions.")
        except Exception as e:
            logger.error(f"Failed to initialize GitHub client: {e}")
            raise

    def get_user_repositories(self) -> List[Dict[str, Any]]:
        """Fetches repositories accessible by the authenticated user."""
        repos_data = []
        try:
            # type='owner' fetches repos owned by the user
            # type='member' fetches repos the user is a collaborator on (including orgs)
            # type='all' fetches both
            for repo in self.gh.repositories(type='all', sort='updated'):
                repos_data.append({
                    "id": repo.id,
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "private": repo.private,
                    "url": repo.html_url,
                    "description": repo.description or "",
                    "last_updated": repo.updated_at if repo.updated_at else None,
                })
            logger.info(f"Fetched {len(repos_data)} repositories.")
            return repos_data
        except Exception as e:
            logger.error(f"Failed to fetch GitHub repositories: {e}")
            return [] # Return empty list on error

    def get_repository_files(self, repo_full_name: str, path: str = '') -> List[Dict[str, Any]]:
        """
        Recursively fetches details of relevant files (code, docs) within a repository path.

        Args:
            repo_full_name: The full name of the repository (e.g., 'owner/repo').
            path: The starting path within the repository (default is root).

        Returns:
            A list of dictionaries, each containing file details (path, sha, url, size).
            Returns an empty list if the repository or path is not found or on error.
        """
        files_list = []
        try:
            owner, repo_name = repo_full_name.split('/')
            repo = self.gh.repository(owner, repo_name)
            if not repo:
                logger.warning(f"Repository '{repo_full_name}' not found.")
                return []
            contents = repo.directory_contents(directory_path=path) # Use directory_contents for clarity
            
            # contents returns a list of tuples (name, content_obj)
            for item_name, content_item in contents:
                if not isinstance(content_item, Contents):
                    continue

                if content_item.type == 'dir':
                    # Check if the directory name is in the skipped list
                    if content_item.name in self.SKIPPED_DIRS:
                        logger.debug(f"Skipping directory: {content_item.path}")
                        continue # Skip recursion for this directory
                    
                    # Recursively fetch contents of subdirectory
                    files_list.extend(self.get_repository_files(repo_full_name, path=content_item.path))
                elif content_item.type == 'file':
                    # Check if the file extension is relevant and size is within limits
                    file_extension = '.' + content_item.name.split('.')[-1].lower() if '.' in content_item.name else ''
                    is_code = file_extension in CODE_EXTENSIONS
                    is_doc = file_extension in DOC_EXTENSIONS
                    
                    if (is_code or is_doc) and content_item.size <= MAX_FILE_SIZE:
                        files_list.append({
                            "path": content_item.path,
                            "sha": content_item.sha,
                            "url": content_item.html_url,
                            "size": content_item.size,
                            "type": "code" if is_code else "doc"
                        })
                    elif content_item.size > MAX_FILE_SIZE:
                         logger.debug(f"Skipping large file: {content_item.path} ({content_item.size} bytes)")
                    else:
                         logger.debug(f"Skipping irrelevant file type: {content_item.path}")

        except (NotFoundError, ForbiddenError) as e:
             logger.warning(f"Cannot access path '{path}' in '{repo_full_name}': {e}")
        except Exception as e:
            logger.error(f"Failed to get files for {repo_full_name} at path '{path}': {e}")
            # Return what we have collected so far in case of partial failure
        
        return files_list

    def get_file_content(self, repo_full_name: str, file_path: str) -> Optional[str]:
        """
        Fetches the decoded content of a specific file.

        Args:
            repo_full_name: The full name of the repository (e.g., 'owner/repo').
            file_path: The path to the file within the repository.

        Returns:
            The decoded file content as a string, or None if fetching fails or file is too large.
        """
        try:
            owner, repo_name = repo_full_name.split('/')
            repo = self.gh.repository(owner, repo_name)
            if not repo:
                logger.warning(f"Repository '{repo_full_name}' not found when fetching file '{file_path}'.")
                return None
                
            content_item = repo.file_contents(path=file_path) # Use file_contents for clarity

            if not content_item or not isinstance(content_item, Contents) or content_item.type != 'file':
                logger.warning(f"File '{file_path}' not found or is not a file in '{repo_full_name}'.")
                return None
            
            if content_item.size > MAX_FILE_SIZE:
                logger.warning(f"File '{file_path}' in '{repo_full_name}' exceeds max size ({content_item.size} > {MAX_FILE_SIZE}). Skipping content fetch.")
                return None

            # Content is base64 encoded
            if content_item.content:
                try:
                    decoded_content = base64.b64decode(content_item.content).decode('utf-8')
                    return decoded_content
                except UnicodeDecodeError:
                    logger.warning(f"Could not decode file '{file_path}' in '{repo_full_name}' as UTF-8. Trying with 'latin-1'.")
                    try:
                        # Try a fallback encoding
                        decoded_content = base64.b64decode(content_item.content).decode('latin-1')
                        return decoded_content
                    except Exception as decode_err:
                        logger.error(f"Failed to decode file '{file_path}' with fallback encoding: {decode_err}")
                        return None # Give up if fallback fails
            else:
                logger.warning(f"No content returned for file '{file_path}' in '{repo_full_name}'. It might be empty.")
                return "" # Return empty string for empty files

        except (NotFoundError, ForbiddenError) as e:
             logger.warning(f"Cannot access file '{file_path}' in '{repo_full_name}': {e}")
             return None
        except Exception as e:
            logger.error(f"Failed to get content for file '{file_path}' in '{repo_full_name}': {e}")
            return None 
