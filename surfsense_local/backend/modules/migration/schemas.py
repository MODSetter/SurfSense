from datetime import datetime
from typing import Literal

from pydantic import BaseModel, TypeAdapter, model_validator


class ExportedCitation(BaseModel):
    title: str


class ExportedMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    citations: list[ExportedCitation]
    created_at: datetime


class ExportedThread(BaseModel):
    id: int
    title: str
    created_at: datetime
    messages: list[ExportedMessage]


ExportedThreads = TypeAdapter(list[ExportedThread])


class ManifestDocument(BaseModel):
    id: int
    path: str
    title: str
    source: str


class ManifestWorkspace(BaseModel):
    id: int
    name: str
    chats: str
    documents: list[ManifestDocument]

    @model_validator(mode="after")
    def paths_stay_under_this_workspace(self) -> "ManifestWorkspace":
        """Trust boundary: the manifest decides which archive members get opened."""
        prefix = f"workspaces/{self.id}/documents/"
        if self.chats != f"workspaces/{self.id}/chats.json":
            raise ValueError(f"chats must be workspaces/{self.id}/chats.json")
        for document in self.documents:
            path = document.path
            if (
                not path.startswith(prefix)
                or "\\" in path
                or ".." in path.split("/")
                or not path.endswith(".md")
            ):
                raise ValueError(f"{path!r} is outside {prefix}")
        return self


class Manifest(BaseModel):
    """`manifest.json` of a contract-3 export bundle."""

    format: Literal["surfsense-export/1"]
    workspaces: list[ManifestWorkspace]


class ImportedWorkspace(BaseModel):
    id: int
    cloud_id: int
    name: str


class ImportAccepted(BaseModel):
    workspaces: list[ImportedWorkspace]
