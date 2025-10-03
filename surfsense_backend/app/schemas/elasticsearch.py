from pydantic import BaseModel, Field


class ElasticsearchConnectorConfig(BaseModel):
    """Configuration for Elasticsearch connector"""

    hostname: str = Field(..., description="Elasticsearch hostname")
    port: int = Field(default=9200, description="Elasticsearch port")
    username: str | None = Field(
        default=None, description="Username for authentication"
    )
    password: str | None = Field(
        default=None, description="Password for authentication"
    )
    api_key: str | None = Field(default=None, description="API key for authentication")
    ssl_enabled: bool = Field(default=True, description="Whether to use SSL/TLS")
    indices: list[str] | None = Field(
        default=None, description="Specific indices to search (optional)"
    )
    query: str = Field(default="*", description="Default search query")
    search_fields: list[str] | None = Field(
        default=None, description="Specific fields to search in"
    )
    max_documents: int = Field(
        default=1000, description="Maximum number of documents to retrieve"
    )


class ElasticsearchTestConnectionRequest(BaseModel):
    """Request model for testing Elasticsearch connection"""

    hostname: str
    port: int = 9200
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    ssl_enabled: bool = True


class ElasticsearchTestConnectionResponse(BaseModel):
    """Response model for Elasticsearch connection test"""

    success: bool
    cluster_name: str | None = None
    version: str | None = None
    indices_count: int | None = None
    error: str | None = None


class ElasticsearchIndicesResponse(BaseModel):
    """Response model for Elasticsearch indices list"""

    success: bool
    indices: list[str] | None = None
    error: str | None = None
