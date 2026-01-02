"""Schemas for Google Drive connector."""

from pydantic import BaseModel, Field


class DriveItem(BaseModel):
    """Represents a Google Drive file or folder."""

    id: str = Field(..., description="Google Drive item ID")
    name: str = Field(..., description="Item display name")


class GoogleDriveIndexRequest(BaseModel):
    """Request body for indexing Google Drive content."""

    folders: list[DriveItem] = Field(
        default_factory=list, description="List of folders to index"
    )
    files: list[DriveItem] = Field(
        default_factory=list, description="List of specific files to index"
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
