"""
Obsidian Connector Credentials Schema.

Obsidian is a local-first note-taking app that stores notes as markdown files.
This connector supports indexing from local file system (self-hosted only).
"""

from pydantic import BaseModel, field_validator


class ObsidianAuthCredentialsBase(BaseModel):
    """
    Credentials/configuration for the Obsidian connector.

    Since Obsidian vaults are local directories, this schema primarily
    holds the vault path and configuration options rather than API tokens.
    """

    vault_path: str
    vault_name: str | None = None
    exclude_folders: list[str] | None = None
    include_attachments: bool = False

    @field_validator("vault_path")
    @classmethod
    def validate_vault_path(cls, v: str) -> str:
        """Ensure vault path is provided and stripped of whitespace."""
        if not v or not v.strip():
            raise ValueError("Vault path is required")
        return v.strip()

    @field_validator("exclude_folders", mode="before")
    @classmethod
    def parse_exclude_folders(cls, v):
        """Parse exclude_folders from string if needed."""
        if v is None:
            return [".trash", ".obsidian", "templates"]
        if isinstance(v, str):
            return [f.strip() for f in v.split(",") if f.strip()]
        return v

    def to_dict(self) -> dict:
        """Convert credentials to dictionary for storage."""
        return {
            "vault_path": self.vault_path,
            "vault_name": self.vault_name,
            "exclude_folders": self.exclude_folders,
            "include_attachments": self.include_attachments,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ObsidianAuthCredentialsBase":
        """Create credentials from dictionary."""
        return cls(
            vault_path=data.get("vault_path", ""),
            vault_name=data.get("vault_name"),
            exclude_folders=data.get("exclude_folders"),
            include_attachments=data.get("include_attachments", False),
        )
