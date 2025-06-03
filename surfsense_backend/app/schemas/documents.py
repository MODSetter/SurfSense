from typing import List
from pydantic import BaseModel, ConfigDict
from app.db import DocumentType
from datetime import datetime

class ExtensionDocumentMetadata(BaseModel):
    BrowsingSessionId: str
    VisitedWebPageURL: str
    VisitedWebPageTitle: str
    VisitedWebPageDateWithTimeInISOString: str
    VisitedWebPageReffererURL: str
    VisitedWebPageVisitDurationInMilliseconds: str

class ExtensionDocumentContent(BaseModel):
    metadata: ExtensionDocumentMetadata
    pageContent: str

class DocumentBase(BaseModel):
    document_type: DocumentType
    content: List[ExtensionDocumentContent] | List[str] | str  # Updated to allow string content
    search_space_id: int

class DocumentsCreate(DocumentBase):
    pass

class DocumentUpdate(DocumentBase):
    pass

class DocumentRead(BaseModel):
    id: int
    title: str
    document_type: DocumentType
    document_metadata: dict
    content: str  # Changed to string to match frontend
    created_at: datetime
    search_space_id: int
    
    model_config = ConfigDict(from_attributes=True)

