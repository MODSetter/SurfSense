"""Schemas for Google Drive connector."""

from pydantic import BaseModel, Field


class DriveItem(BaseModel):
    """Represents a Google Drive file or folder."""

    id: str = Field(..., description="Google Drive item ID")
    name: str = Field(..., description="Item display name")


class GoogleDriveIndexingOptions(BaseModel):
    """Indexing options for Google Drive connector."""

    max_files_per_folder: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of files to index from each folder (1-1000)",
    )
    incremental_sync: bool = Field(
        default=True,
        description="Only sync changes since last index (faster). Disable for a full re-index.",
    )
    include_subfolders: bool = Field(
        default=True,
        description="Recursively index files in subfolders of selected folders",
    )


class GoogleDriveIndexRequest(BaseModel):
    """Request body for indexing Google Drive content."""

    folders: list[DriveItem] = Field(
        default_factory=list, description="List of folders to index"
    )
    files: list[DriveItem] = Field(
        default_factory=list, description="List of specific files to index"
    )
    indexing_options: GoogleDriveIndexingOptions = Field(
        default_factory=GoogleDriveIndexingOptions,
        description="Indexing configuration options",
    )

    def has_items(self) -> bool:
        """Check if any items are selected."""
        return len(self.folders) > 0 or len(self.files) > 0

    def get_folder_ids(self) -> list[str]:
        """Get list of folder IDs."""
        return [folder.id for folder in self.folders]

    def get_folder_names(self) -> list[str]:
        """Get list of folder names."""
        return [folder.name for folder in self.folders]

    def get_file_ids(self) -> list[str]:
        """Get list of file IDs."""
        return [file.id for file in self.files]

    def get_file_names(self) -> list[str]:
        """Get list of file names."""
        return [file.name for file in self.files]
