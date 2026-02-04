from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from enum import Enum

from fastapi import Depends
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    JSON,
    TIMESTAMP,
    Boolean,
    Column,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, relationship

from app.config import config

if config.AUTH_TYPE == "GOOGLE":
    from fastapi_users.db import SQLAlchemyBaseOAuthAccountTableUUID

DATABASE_URL = config.DATABASE_URL


class DocumentType(str, Enum):
    EXTENSION = "EXTENSION"
    CRAWLED_URL = "CRAWLED_URL"
    FILE = "FILE"
    SLACK_CONNECTOR = "SLACK_CONNECTOR"
    TEAMS_CONNECTOR = "TEAMS_CONNECTOR"
    NOTION_CONNECTOR = "NOTION_CONNECTOR"
    YOUTUBE_VIDEO = "YOUTUBE_VIDEO"
    GITHUB_CONNECTOR = "GITHUB_CONNECTOR"
    LINEAR_CONNECTOR = "LINEAR_CONNECTOR"
    DISCORD_CONNECTOR = "DISCORD_CONNECTOR"
    JIRA_CONNECTOR = "JIRA_CONNECTOR"
    CONFLUENCE_CONNECTOR = "CONFLUENCE_CONNECTOR"
    CLICKUP_CONNECTOR = "CLICKUP_CONNECTOR"
    GOOGLE_CALENDAR_CONNECTOR = "GOOGLE_CALENDAR_CONNECTOR"
    GOOGLE_GMAIL_CONNECTOR = "GOOGLE_GMAIL_CONNECTOR"
    GOOGLE_DRIVE_FILE = "GOOGLE_DRIVE_FILE"
    AIRTABLE_CONNECTOR = "AIRTABLE_CONNECTOR"
    LUMA_CONNECTOR = "LUMA_CONNECTOR"
    ELASTICSEARCH_CONNECTOR = "ELASTICSEARCH_CONNECTOR"
    BOOKSTACK_CONNECTOR = "BOOKSTACK_CONNECTOR"
    CIRCLEBACK = "CIRCLEBACK"
    OBSIDIAN_CONNECTOR = "OBSIDIAN_CONNECTOR"
    NOTE = "NOTE"
    COMPOSIO_GOOGLE_DRIVE_CONNECTOR = "COMPOSIO_GOOGLE_DRIVE_CONNECTOR"
    COMPOSIO_GMAIL_CONNECTOR = "COMPOSIO_GMAIL_CONNECTOR"
    COMPOSIO_GOOGLE_CALENDAR_CONNECTOR = "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR"


class SearchSourceConnectorType(str, Enum):
    SERPER_API = "SERPER_API"  # NOT IMPLEMENTED YET : DON'T REMEMBER WHY : MOST PROBABLY BECAUSE WE NEED TO CRAWL THE RESULTS RETURNED BY IT
    TAVILY_API = "TAVILY_API"
    SEARXNG_API = "SEARXNG_API"
    LINKUP_API = "LINKUP_API"
    BAIDU_SEARCH_API = "BAIDU_SEARCH_API"  # Baidu AI Search API for Chinese web search
    SLACK_CONNECTOR = "SLACK_CONNECTOR"
    TEAMS_CONNECTOR = "TEAMS_CONNECTOR"
    NOTION_CONNECTOR = "NOTION_CONNECTOR"
    GITHUB_CONNECTOR = "GITHUB_CONNECTOR"
    LINEAR_CONNECTOR = "LINEAR_CONNECTOR"
    DISCORD_CONNECTOR = "DISCORD_CONNECTOR"
    JIRA_CONNECTOR = "JIRA_CONNECTOR"
    CONFLUENCE_CONNECTOR = "CONFLUENCE_CONNECTOR"
    CLICKUP_CONNECTOR = "CLICKUP_CONNECTOR"
    GOOGLE_CALENDAR_CONNECTOR = "GOOGLE_CALENDAR_CONNECTOR"
    GOOGLE_GMAIL_CONNECTOR = "GOOGLE_GMAIL_CONNECTOR"
    GOOGLE_DRIVE_CONNECTOR = "GOOGLE_DRIVE_CONNECTOR"
    AIRTABLE_CONNECTOR = "AIRTABLE_CONNECTOR"
    LUMA_CONNECTOR = "LUMA_CONNECTOR"
    ELASTICSEARCH_CONNECTOR = "ELASTICSEARCH_CONNECTOR"
    WEBCRAWLER_CONNECTOR = "WEBCRAWLER_CONNECTOR"
    BOOKSTACK_CONNECTOR = "BOOKSTACK_CONNECTOR"
    CIRCLEBACK_CONNECTOR = "CIRCLEBACK_CONNECTOR"
    OBSIDIAN_CONNECTOR = (
        "OBSIDIAN_CONNECTOR"  # Self-hosted only - Local Obsidian vault indexing
    )
    MCP_CONNECTOR = "MCP_CONNECTOR"  # Model Context Protocol - User-defined API tools
    COMPOSIO_GOOGLE_DRIVE_CONNECTOR = "COMPOSIO_GOOGLE_DRIVE_CONNECTOR"
    COMPOSIO_GMAIL_CONNECTOR = "COMPOSIO_GMAIL_CONNECTOR"
    COMPOSIO_GOOGLE_CALENDAR_CONNECTOR = "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR"


class PodcastStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class LiteLLMProvider(str, Enum):
    """
    Enum for LLM providers supported by LiteLLM.
    """

    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    GOOGLE = "GOOGLE"
    AZURE_OPENAI = "AZURE_OPENAI"
    BEDROCK = "BEDROCK"
    VERTEX_AI = "VERTEX_AI"
    GROQ = "GROQ"
    COHERE = "COHERE"
    MISTRAL = "MISTRAL"
    DEEPSEEK = "DEEPSEEK"
    XAI = "XAI"
    OPENROUTER = "OPENROUTER"
    TOGETHER_AI = "TOGETHER_AI"
    FIREWORKS_AI = "FIREWORKS_AI"
    REPLICATE = "REPLICATE"
    PERPLEXITY = "PERPLEXITY"
    OLLAMA = "OLLAMA"
    ALIBABA_QWEN = "ALIBABA_QWEN"
    MOONSHOT = "MOONSHOT"
    ZHIPU = "ZHIPU"
    ANYSCALE = "ANYSCALE"
    DEEPINFRA = "DEEPINFRA"
    CEREBRAS = "CEREBRAS"
    SAMBANOVA = "SAMBANOVA"
    AI21 = "AI21"
    CLOUDFLARE = "CLOUDFLARE"
    DATABRICKS = "DATABRICKS"
    COMETAPI = "COMETAPI"
    HUGGINGFACE = "HUGGINGFACE"
    CUSTOM = "CUSTOM"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class IncentiveTaskType(str, Enum):
    """
    Enum for incentive task types that users can complete to earn free pages.
    Each task can only be completed once per user.

    When adding new tasks:
    1. Add a new enum value here
    2. Add the task configuration to INCENTIVE_TASKS_CONFIG below
    3. Create an Alembic migration to add the enum value to PostgreSQL
    """

    GITHUB_STAR = "GITHUB_STAR"
    REDDIT_FOLLOW = "REDDIT_FOLLOW"
    DISCORD_JOIN = "DISCORD_JOIN"
    # Future tasks can be added here:
    # GITHUB_ISSUE = "GITHUB_ISSUE"
    # SOCIAL_SHARE = "SOCIAL_SHARE"
    # REFER_FRIEND = "REFER_FRIEND"


# Centralized configuration for incentive tasks
# This makes it easy to add new tasks without changing code in multiple places
INCENTIVE_TASKS_CONFIG = {
    IncentiveTaskType.GITHUB_STAR: {
        "title": "Star our GitHub repository",
        "description": "Show your support by starring SurfSense on GitHub",
        "pages_reward": 100,
        "action_url": "https://github.com/MODSetter/SurfSense",
    },
    IncentiveTaskType.REDDIT_FOLLOW: {
        "title": "Join our Subreddit",
        "description": "Join the SurfSense community on Reddit",
        "pages_reward": 100,
        "action_url": "https://www.reddit.com/r/SurfSense/",
    },
    IncentiveTaskType.DISCORD_JOIN: {
        "title": "Join our Discord",
        "description": "Join the SurfSense community on Discord",
        "pages_reward": 100,
        "action_url": "https://discord.gg/ejRNvftDp9",
    },
    # Future tasks can be configured here:
    # IncentiveTaskType.GITHUB_ISSUE: {
    #     "title": "Create an issue",
    #     "description": "Help improve SurfSense by reporting bugs or suggesting features",
    #     "pages_reward": 50,
    #     "action_url": "https://github.com/MODSetter/SurfSense/issues/new/choose",
    # },
}


class Permission(str, Enum):
    """
    Granular permissions for search space resources.
    Use '*' (FULL_ACCESS) to grant all permissions.
    """

    # Documents
    DOCUMENTS_CREATE = "documents:create"
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_UPDATE = "documents:update"
    DOCUMENTS_DELETE = "documents:delete"

    # Chats
    CHATS_CREATE = "chats:create"
    CHATS_READ = "chats:read"
    CHATS_UPDATE = "chats:update"
    CHATS_DELETE = "chats:delete"

    # Comments
    COMMENTS_CREATE = "comments:create"
    COMMENTS_READ = "comments:read"
    COMMENTS_DELETE = "comments:delete"

    # LLM Configs
    LLM_CONFIGS_CREATE = "llm_configs:create"
    LLM_CONFIGS_READ = "llm_configs:read"
    LLM_CONFIGS_UPDATE = "llm_configs:update"
    LLM_CONFIGS_DELETE = "llm_configs:delete"

    # Podcasts
    PODCASTS_CREATE = "podcasts:create"
    PODCASTS_READ = "podcasts:read"
    PODCASTS_UPDATE = "podcasts:update"
    PODCASTS_DELETE = "podcasts:delete"

    # Connectors
    CONNECTORS_CREATE = "connectors:create"
    CONNECTORS_READ = "connectors:read"
    CONNECTORS_UPDATE = "connectors:update"
    CONNECTORS_DELETE = "connectors:delete"

    # Logs
    LOGS_READ = "logs:read"
    LOGS_DELETE = "logs:delete"

    # Members
    MEMBERS_INVITE = "members:invite"
    MEMBERS_VIEW = "members:view"
    MEMBERS_REMOVE = "members:remove"
    MEMBERS_MANAGE_ROLES = "members:manage_roles"

    # Roles
    ROLES_CREATE = "roles:create"
    ROLES_READ = "roles:read"
    ROLES_UPDATE = "roles:update"
    ROLES_DELETE = "roles:delete"

    # Search Space Settings
    SETTINGS_VIEW = "settings:view"
    SETTINGS_UPDATE = "settings:update"
    SETTINGS_DELETE = "settings:delete"  # Delete the entire search space

    # Public Sharing
    PUBLIC_SHARING_VIEW = "public_sharing:view"
    PUBLIC_SHARING_CREATE = "public_sharing:create"
    PUBLIC_SHARING_DELETE = "public_sharing:delete"

    # Full access wildcard
    FULL_ACCESS = "*"


# Predefined role permission sets for convenience
# Note: Only Owner, Editor, and Viewer roles are supported.
# Owner has full access (*), Editor can do everything except delete, Viewer has read-only access.
DEFAULT_ROLE_PERMISSIONS = {
    "Owner": [Permission.FULL_ACCESS.value],
    "Editor": [
        # Documents (no delete)
        Permission.DOCUMENTS_CREATE.value,
        Permission.DOCUMENTS_READ.value,
        Permission.DOCUMENTS_UPDATE.value,
        # Chats (no delete)
        Permission.CHATS_CREATE.value,
        Permission.CHATS_READ.value,
        Permission.CHATS_UPDATE.value,
        # Comments (no delete)
        Permission.COMMENTS_CREATE.value,
        Permission.COMMENTS_READ.value,
        # LLM Configs (no delete)
        Permission.LLM_CONFIGS_CREATE.value,
        Permission.LLM_CONFIGS_READ.value,
        Permission.LLM_CONFIGS_UPDATE.value,
        # Podcasts (no delete)
        Permission.PODCASTS_CREATE.value,
        Permission.PODCASTS_READ.value,
        Permission.PODCASTS_UPDATE.value,
        # Connectors (no delete)
        Permission.CONNECTORS_CREATE.value,
        Permission.CONNECTORS_READ.value,
        Permission.CONNECTORS_UPDATE.value,
        # Logs (read only)
        Permission.LOGS_READ.value,
        # Members (can invite and view only, cannot manage roles or remove)
        Permission.MEMBERS_INVITE.value,
        Permission.MEMBERS_VIEW.value,
        # Roles (read only - cannot create, update, or delete)
        Permission.ROLES_READ.value,
        # Settings (view only, no update or delete)
        Permission.SETTINGS_VIEW.value,
        # Public Sharing (can create and view, no delete)
        Permission.PUBLIC_SHARING_VIEW.value,
        Permission.PUBLIC_SHARING_CREATE.value,
    ],
    "Viewer": [
        # Documents (read only)
        Permission.DOCUMENTS_READ.value,
        # Chats (read only)
        Permission.CHATS_READ.value,
        # Comments (can create and read, but not delete)
        Permission.COMMENTS_CREATE.value,
        Permission.COMMENTS_READ.value,
        # LLM Configs (read only)
        Permission.LLM_CONFIGS_READ.value,
        # Podcasts (read only)
        Permission.PODCASTS_READ.value,
        # Connectors (read only)
        Permission.CONNECTORS_READ.value,
        # Logs (read only)
        Permission.LOGS_READ.value,
        # Members (view only)
        Permission.MEMBERS_VIEW.value,
        # Roles (read only)
        Permission.ROLES_READ.value,
        # Settings (view only)
        Permission.SETTINGS_VIEW.value,
        # Public Sharing (view only)
        Permission.PUBLIC_SHARING_VIEW.value,
    ],
}


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    @declared_attr
    def created_at(cls):  # noqa: N805
        return Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            default=lambda: datetime.now(UTC),
            index=True,
        )


class BaseModel(Base):
    __abstract__ = True
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)


class NewChatMessageRole(str, Enum):
    """Role enum for new chat messages."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatVisibility(str, Enum):
    """
    Visibility/sharing level for chat threads.

    PRIVATE: Only the creator can see/access the chat (default)
    SEARCH_SPACE: All members of the search space can see/access the chat
    PUBLIC: (Future) Anyone with the link can access the chat
    """

    PRIVATE = "PRIVATE"
    SEARCH_SPACE = "SEARCH_SPACE"
    # PUBLIC = "PUBLIC"  # Reserved for future implementation


class NewChatThread(BaseModel, TimestampMixin):
    """
    Thread model for the new chat feature using assistant-ui.
    Each thread represents a conversation with message history.
    LangGraph checkpointer uses thread_id for state persistence.
    """

    __tablename__ = "new_chat_threads"

    title = Column(String(500), nullable=False, default="New Chat", index=True)
    archived = Column(Boolean, nullable=False, default=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )

    # Visibility/sharing control
    visibility = Column(
        SQLAlchemyEnum(ChatVisibility),
        nullable=False,
        default=ChatVisibility.PRIVATE,
        server_default="PRIVATE",
        index=True,
    )

    # Foreign keys
    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )

    # Track who created this chat thread (for visibility filtering)
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,  # Nullable for existing records before migration
        index=True,
    )

    # Clone tracking - for audit and history bootstrap
    cloned_from_thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cloned_from_snapshot_id = Column(
        Integer,
        ForeignKey("public_chat_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cloned_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    # Flag to bootstrap LangGraph checkpointer with DB messages on first message
    needs_history_bootstrap = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # Relationships
    search_space = relationship("SearchSpace", back_populates="new_chat_threads")
    created_by = relationship("User", back_populates="new_chat_threads")
    messages = relationship(
        "NewChatMessage",
        back_populates="thread",
        order_by="NewChatMessage.created_at",
        cascade="all, delete-orphan",
    )
    snapshots = relationship(
        "PublicChatSnapshot",
        back_populates="thread",
        cascade="all, delete-orphan",
        foreign_keys="[PublicChatSnapshot.thread_id]",
    )


class NewChatMessage(BaseModel, TimestampMixin):
    """
    Message model for the new chat feature.
    Stores individual messages in assistant-ui format.
    """

    __tablename__ = "new_chat_messages"

    role = Column(SQLAlchemyEnum(NewChatMessageRole), nullable=False)
    # Content stored as JSONB to support rich content (text, tool calls, etc.)
    content = Column(JSONB, nullable=False)

    # Foreign key to thread
    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Track who sent this message (for shared chats)
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    thread = relationship("NewChatThread", back_populates="messages")
    author = relationship("User")
    comments = relationship(
        "ChatComment",
        back_populates="message",
        cascade="all, delete-orphan",
    )


class PublicChatSnapshot(BaseModel, TimestampMixin):
    """
    Immutable snapshot of a chat thread for public sharing.

    Each snapshot is a frozen copy of the chat at a specific point in time.
    The snapshot_data JSONB contains all messages and metadata needed to
    render the public chat without querying the original thread.
    """

    __tablename__ = "public_chat_snapshots"

    # Link to original thread - CASCADE DELETE when thread is deleted
    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Public access token (unique URL identifier)
    share_token = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    content_hash = Column(
        String(64),
        nullable=False,
        index=True,
    )

    snapshot_data = Column(JSONB, nullable=False)

    message_ids = Column(ARRAY(Integer), nullable=False)

    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    thread = relationship(
        "NewChatThread",
        back_populates="snapshots",
        foreign_keys="[PublicChatSnapshot.thread_id]",
    )
    created_by = relationship("User")

    # Constraints
    __table_args__ = (
        # Prevent duplicate snapshots of the same content for the same thread
        UniqueConstraint(
            "thread_id", "content_hash", name="uq_snapshot_thread_content_hash"
        ),
    )


class ChatComment(BaseModel, TimestampMixin):
    """
    Comment model for comments on AI chat responses.
    Supports one level of nesting (replies to comments, but no replies to replies).
    """

    __tablename__ = "chat_comments"

    message_id = Column(
        Integer,
        ForeignKey("new_chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized thread_id for efficient Electric SQL subscriptions (one per thread)
    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id = Column(
        Integer,
        ForeignKey("chat_comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content = Column(Text, nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )

    # Relationships
    message = relationship("NewChatMessage", back_populates="comments")
    thread = relationship("NewChatThread")
    author = relationship("User")
    parent = relationship(
        "ChatComment", remote_side="ChatComment.id", backref="replies"
    )
    mentions = relationship(
        "ChatCommentMention",
        back_populates="comment",
        cascade="all, delete-orphan",
    )


class ChatCommentMention(BaseModel, TimestampMixin):
    """
    Tracks @mentions in chat comments for notification purposes.
    """

    __tablename__ = "chat_comment_mentions"

    comment_id = Column(
        Integer,
        ForeignKey("chat_comments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mentioned_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    comment = relationship("ChatComment", back_populates="mentions")
    mentioned_user = relationship("User")


class ChatSessionState(BaseModel):
    """
    Tracks real-time session state for shared chat collaboration.
    One record per thread, synced via Electric SQL.
    """

    __tablename__ = "chat_session_state"

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    ai_responding_to_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    thread = relationship("NewChatThread")
    ai_responding_to_user = relationship("User")


class MemoryCategory(str, Enum):
    """Categories for user memories."""

    # Using lowercase keys to match PostgreSQL enum values
    preference = "preference"  # User preferences (e.g., "prefers dark mode")
    fact = "fact"  # Facts about the user (e.g., "is a Python developer")
    instruction = (
        "instruction"  # Standing instructions (e.g., "always respond in bullet points")
    )
    context = "context"  # Contextual information (e.g., "working on project X")


class UserMemory(BaseModel, TimestampMixin):
    """
    Stores facts, preferences, and context about users for personalized AI responses.
    Similar to Claude's memory feature - enables the AI to remember user information
    across conversations.
    """

    __tablename__ = "user_memories"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional association with a search space (if memory is space-specific)
    search_space_id = Column(
        Integer,
        ForeignKey("searchspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # The actual memory content
    memory_text = Column(Text, nullable=False)
    # Category for organization and filtering
    category = Column(
        SQLAlchemyEnum(MemoryCategory),
        nullable=False,
        default=MemoryCategory.fact,
    )
    # Vector embedding for semantic search
    embedding = Column(Vector(config.embedding_model_instance.dimension))

    # Track when memory was last updated
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )

    # Relationships
    user = relationship("User", back_populates="memories")
    search_space = relationship("SearchSpace", back_populates="user_memories")


class Document(BaseModel, TimestampMixin):
    __tablename__ = "documents"

    title = Column(String, nullable=False, index=True)
    document_type = Column(SQLAlchemyEnum(DocumentType), nullable=False)
    document_metadata = Column(JSON, nullable=True)

    content = Column(Text, nullable=False)
    content_hash = Column(String, nullable=False, index=True, unique=True)
    unique_identifier_hash = Column(String, nullable=True, index=True, unique=True)
    embedding = Column(Vector(config.embedding_model_instance.dimension))

    # BlockNote live editing state (NULL when never edited)
    blocknote_document = Column(JSONB, nullable=True)

    # blocknote background reindex flag
    content_needs_reindexing = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    # Track when document was last updated by indexers, processors, or editor
    updated_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )

    # Track who created/uploaded this document
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,  # Nullable for backward compatibility with existing records
        index=True,
    )

    # Track which connector created this document (for cleanup on connector deletion)
    connector_id = Column(
        Integer,
        ForeignKey("search_source_connectors.id", ondelete="SET NULL"),
        nullable=True,  # Nullable for manually uploaded docs without connector
        index=True,
    )

    # Relationships
    search_space = relationship("SearchSpace", back_populates="documents")
    created_by = relationship("User", back_populates="documents")
    connector = relationship("SearchSourceConnector", back_populates="documents")
    chunks = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(BaseModel, TimestampMixin):
    __tablename__ = "chunks"

    content = Column(Text, nullable=False)
    embedding = Column(Vector(config.embedding_model_instance.dimension))

    document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    document = relationship("Document", back_populates="chunks")


class SurfsenseDocsDocument(BaseModel, TimestampMixin):
    """
    Surfsense documentation storage.
    Indexed at migration time from MDX files.
    """

    __tablename__ = "surfsense_docs_documents"

    source = Column(
        String, nullable=False, unique=True, index=True
    )  # File path: "connectors/slack.mdx"
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String, nullable=False, index=True)  # For detecting changes
    embedding = Column(Vector(config.embedding_model_instance.dimension))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    chunks = relationship(
        "SurfsenseDocsChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class SurfsenseDocsChunk(BaseModel, TimestampMixin):
    """Chunk storage for Surfsense documentation."""

    __tablename__ = "surfsense_docs_chunks"

    content = Column(Text, nullable=False)
    embedding = Column(Vector(config.embedding_model_instance.dimension))

    document_id = Column(
        Integer,
        ForeignKey("surfsense_docs_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    document = relationship("SurfsenseDocsDocument", back_populates="chunks")


class Podcast(BaseModel, TimestampMixin):
    """Podcast model for storing generated podcasts."""

    __tablename__ = "podcasts"

    title = Column(String(500), nullable=False)
    podcast_transcript = Column(JSONB, nullable=True)
    file_location = Column(Text, nullable=True)
    status = Column(
        SQLAlchemyEnum(
            PodcastStatus,
            name="podcast_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PodcastStatus.READY,
        server_default="ready",
        index=True,
    )

    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )
    search_space = relationship("SearchSpace", back_populates="podcasts")

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    thread = relationship("NewChatThread")


class SearchSpace(BaseModel, TimestampMixin):
    __tablename__ = "searchspaces"

    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)

    citations_enabled = Column(
        Boolean, nullable=False, default=True
    )  # Enable/disable citations
    qna_custom_instructions = Column(
        Text, nullable=True, default=""
    )  # User's custom instructions

    # Search space-level LLM preferences (shared by all members)
    # Note: ID values:
    #   - 0: Auto mode (uses LiteLLM Router for load balancing) - default for new search spaces
    #   - Negative IDs: Global configs from YAML
    #   - Positive IDs: Custom configs from DB (NewLLMConfig table)
    agent_llm_id = Column(
        Integer, nullable=True, default=0
    )  # For agent/chat operations, defaults to Auto mode
    document_summary_llm_id = Column(
        Integer, nullable=True, default=0
    )  # For document summarization, defaults to Auto mode

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    user = relationship("User", back_populates="search_spaces")

    documents = relationship(
        "Document",
        back_populates="search_space",
        order_by="Document.id",
        cascade="all, delete-orphan",
    )
    new_chat_threads = relationship(
        "NewChatThread",
        back_populates="search_space",
        order_by="NewChatThread.updated_at.desc()",
        cascade="all, delete-orphan",
    )
    podcasts = relationship(
        "Podcast",
        back_populates="search_space",
        order_by="Podcast.id.desc()",
        cascade="all, delete-orphan",
    )
    logs = relationship(
        "Log",
        back_populates="search_space",
        order_by="Log.id",
        cascade="all, delete-orphan",
    )
    notifications = relationship(
        "Notification",
        back_populates="search_space",
        order_by="Notification.created_at.desc()",
        cascade="all, delete-orphan",
    )
    search_source_connectors = relationship(
        "SearchSourceConnector",
        back_populates="search_space",
        order_by="SearchSourceConnector.id",
        cascade="all, delete-orphan",
    )
    new_llm_configs = relationship(
        "NewLLMConfig",
        back_populates="search_space",
        order_by="NewLLMConfig.id",
        cascade="all, delete-orphan",
    )

    # RBAC relationships
    roles = relationship(
        "SearchSpaceRole",
        back_populates="search_space",
        order_by="SearchSpaceRole.id",
        cascade="all, delete-orphan",
    )
    memberships = relationship(
        "SearchSpaceMembership",
        back_populates="search_space",
        order_by="SearchSpaceMembership.id",
        cascade="all, delete-orphan",
    )
    invites = relationship(
        "SearchSpaceInvite",
        back_populates="search_space",
        order_by="SearchSpaceInvite.id",
        cascade="all, delete-orphan",
    )

    # User memories associated with this search space
    user_memories = relationship(
        "UserMemory",
        back_populates="search_space",
        order_by="UserMemory.updated_at.desc()",
        cascade="all, delete-orphan",
    )


class SearchSourceConnector(BaseModel, TimestampMixin):
    __tablename__ = "search_source_connectors"
    __table_args__ = (
        UniqueConstraint(
            "search_space_id",
            "user_id",
            "connector_type",
            "name",
            name="uq_searchspace_user_connector_type_name",
        ),
    )

    name = Column(String(100), nullable=False, index=True)
    connector_type = Column(SQLAlchemyEnum(SearchSourceConnectorType), nullable=False)
    is_indexable = Column(Boolean, nullable=False, default=False)
    last_indexed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    config = Column(JSON, nullable=False)

    # Periodic indexing fields
    periodic_indexing_enabled = Column(Boolean, nullable=False, default=False)
    indexing_frequency_minutes = Column(Integer, nullable=True)
    next_scheduled_at = Column(TIMESTAMP(timezone=True), nullable=True)

    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )
    search_space = relationship(
        "SearchSpace", back_populates="search_source_connectors"
    )

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )

    # Documents created by this connector (for cleanup on connector deletion)
    documents = relationship("Document", back_populates="connector")


class NewLLMConfig(BaseModel, TimestampMixin):
    """
    New LLM configuration table that combines model settings with prompt configuration.

    This table provides:
    - LLM model configuration (provider, model_name, api_key, etc.)
    - Configurable system instructions (defaults to SURFSENSE_SYSTEM_INSTRUCTIONS)
    - Citation toggle (enable/disable citation instructions)

    Note: SURFSENSE_TOOLS_INSTRUCTIONS is always used and not configurable.
    """

    __tablename__ = "new_llm_configs"

    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)

    # === LLM Model Configuration (from original LLMConfig, excluding 'language') ===
    # Provider from the enum
    provider = Column(SQLAlchemyEnum(LiteLLMProvider), nullable=False)
    # Custom provider name when provider is CUSTOM
    custom_provider = Column(String(100), nullable=True)
    # Just the model name without provider prefix
    model_name = Column(String(100), nullable=False)
    # API Key should be encrypted before storing
    api_key = Column(String, nullable=False)
    api_base = Column(String(500), nullable=True)
    # For any other parameters that litellm supports
    litellm_params = Column(JSON, nullable=True, default={})

    # === Prompt Configuration ===
    # Configurable system instructions (defaults to SURFSENSE_SYSTEM_INSTRUCTIONS)
    # Users can customize this from the UI
    system_instructions = Column(
        Text,
        nullable=False,
        default="",  # Empty string means use default SURFSENSE_SYSTEM_INSTRUCTIONS
    )
    # Whether to use the default system instructions when system_instructions is empty
    use_default_system_instructions = Column(Boolean, nullable=False, default=True)

    # Citation toggle - when enabled, SURFSENSE_CITATION_INSTRUCTIONS is injected
    # When disabled, an anti-citation prompt is injected instead
    citations_enabled = Column(Boolean, nullable=False, default=True)

    # === Relationships ===
    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )
    search_space = relationship("SearchSpace", back_populates="new_llm_configs")


class Log(BaseModel, TimestampMixin):
    __tablename__ = "logs"

    level = Column(SQLAlchemyEnum(LogLevel), nullable=False, index=True)
    status = Column(SQLAlchemyEnum(LogStatus), nullable=False, index=True)
    message = Column(Text, nullable=False)
    source = Column(
        String(200), nullable=True, index=True
    )  # Service/component that generated the log
    log_metadata = Column(JSON, nullable=True, default={})  # Additional context data

    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )
    search_space = relationship("SearchSpace", back_populates="logs")


class Notification(BaseModel, TimestampMixin):
    __tablename__ = "notifications"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=True
    )
    type = Column(
        String(50), nullable=False
    )  # 'connector_indexing', 'document_processing', etc.
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    read = Column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )
    notification_metadata = Column("metadata", JSONB, nullable=True, default={})
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )

    user = relationship("User", back_populates="notifications")
    search_space = relationship("SearchSpace", back_populates="notifications")


class UserIncentiveTask(BaseModel, TimestampMixin):
    """
    Tracks completed incentive tasks for users.
    Each user can only complete each task type once.
    When a task is completed, the user's pages_limit is increased.
    """

    __tablename__ = "user_incentive_tasks"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "task_type",
            name="uq_user_incentive_task",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_type = Column(SQLAlchemyEnum(IncentiveTaskType), nullable=False, index=True)
    pages_awarded = Column(Integer, nullable=False)
    completed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    user = relationship("User", back_populates="incentive_tasks")


class SearchSpaceRole(BaseModel, TimestampMixin):
    """
    Custom roles that can be defined per search space.
    Each search space can have multiple roles with different permission sets.
    """

    __tablename__ = "search_space_roles"
    __table_args__ = (
        UniqueConstraint(
            "search_space_id",
            "name",
            name="uq_searchspace_role_name",
        ),
    )

    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    # List of Permission enum values (e.g., ["documents:read", "chats:create"])
    permissions = Column(ARRAY(String), nullable=False, default=[])
    # Whether this role is assigned to new members by default when they join via invite
    is_default = Column(Boolean, nullable=False, default=False)
    # System roles (Owner, Editor, Viewer) cannot be deleted
    is_system_role = Column(Boolean, nullable=False, default=False)

    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )
    search_space = relationship("SearchSpace", back_populates="roles")

    memberships = relationship(
        "SearchSpaceMembership", back_populates="role", passive_deletes=True
    )
    invites = relationship(
        "SearchSpaceInvite", back_populates="role", passive_deletes=True
    )


class SearchSpaceMembership(BaseModel, TimestampMixin):
    """
    Tracks user membership in search spaces with their assigned role.
    Each user can be a member of multiple search spaces with different roles.
    """

    __tablename__ = "search_space_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "search_space_id",
            name="uq_user_searchspace_membership",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )
    role_id = Column(
        Integer,
        ForeignKey("search_space_roles.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Indicates if this user is the original creator/owner of the search space
    is_owner = Column(Boolean, nullable=False, default=False)
    # Timestamp when the user joined (via invite or as creator)
    joined_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # Reference to the invite used to join (null if owner/creator)
    invited_by_invite_id = Column(
        Integer,
        ForeignKey("search_space_invites.id", ondelete="SET NULL"),
        nullable=True,
    )

    user = relationship("User", back_populates="search_space_memberships")
    search_space = relationship("SearchSpace", back_populates="memberships")
    role = relationship("SearchSpaceRole", back_populates="memberships")
    invited_by_invite = relationship(
        "SearchSpaceInvite", back_populates="used_by_memberships"
    )


class SearchSpaceInvite(BaseModel, TimestampMixin):
    """
    Invite links for search spaces.
    Users can create invite links with specific roles that others can use to join.
    """

    __tablename__ = "search_space_invites"

    # Unique invite code (used in invite URLs)
    invite_code = Column(String(64), nullable=False, unique=True, index=True)

    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )
    # Role to assign when invite is used (null means use default role)
    role_id = Column(
        Integer,
        ForeignKey("search_space_roles.id", ondelete="SET NULL"),
        nullable=True,
    )
    # User who created this invite
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Expiration timestamp (null means never expires)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    # Maximum number of times this invite can be used (null means unlimited)
    max_uses = Column(Integer, nullable=True)
    # Number of times this invite has been used
    uses_count = Column(Integer, nullable=False, default=0)
    # Whether this invite is currently active
    is_active = Column(Boolean, nullable=False, default=True)
    # Optional custom name/label for the invite
    name = Column(String(100), nullable=True)

    search_space = relationship("SearchSpace", back_populates="invites")
    role = relationship("SearchSpaceRole", back_populates="invites")
    created_by = relationship("User", back_populates="created_invites")
    used_by_memberships = relationship(
        "SearchSpaceMembership",
        back_populates="invited_by_invite",
        passive_deletes=True,
    )


if config.AUTH_TYPE == "GOOGLE":

    class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
        pass

    class User(SQLAlchemyBaseUserTableUUID, Base):
        oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
            "OAuthAccount", lazy="joined"
        )
        search_spaces = relationship("SearchSpace", back_populates="user")
        notifications = relationship(
            "Notification",
            back_populates="user",
            order_by="Notification.created_at.desc()",
            cascade="all, delete-orphan",
        )

        # RBAC relationships
        search_space_memberships = relationship(
            "SearchSpaceMembership",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        created_invites = relationship(
            "SearchSpaceInvite",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Chat threads created by this user
        new_chat_threads = relationship(
            "NewChatThread",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Documents created/uploaded by this user
        documents = relationship(
            "Document",
            back_populates="created_by",
            passive_deletes=True,
        )

        # User memories for personalized AI responses
        memories = relationship(
            "UserMemory",
            back_populates="user",
            order_by="UserMemory.updated_at.desc()",
            cascade="all, delete-orphan",
        )

        # Incentive tasks completed by this user
        incentive_tasks = relationship(
            "UserIncentiveTask",
            back_populates="user",
            cascade="all, delete-orphan",
        )

        # Page usage tracking for ETL services
        pages_limit = Column(
            Integer,
            nullable=False,
            default=config.PAGES_LIMIT,
            server_default=str(config.PAGES_LIMIT),
        )
        pages_used = Column(Integer, nullable=False, default=0, server_default="0")

        # User profile from OAuth
        display_name = Column(String, nullable=True)
        avatar_url = Column(String, nullable=True)

else:

    class User(SQLAlchemyBaseUserTableUUID, Base):
        search_spaces = relationship("SearchSpace", back_populates="user")
        notifications = relationship(
            "Notification",
            back_populates="user",
            order_by="Notification.created_at.desc()",
            cascade="all, delete-orphan",
        )

        # RBAC relationships
        search_space_memberships = relationship(
            "SearchSpaceMembership",
            back_populates="user",
            cascade="all, delete-orphan",
        )
        created_invites = relationship(
            "SearchSpaceInvite",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Chat threads created by this user
        new_chat_threads = relationship(
            "NewChatThread",
            back_populates="created_by",
            passive_deletes=True,
        )

        # Documents created/uploaded by this user
        documents = relationship(
            "Document",
            back_populates="created_by",
            passive_deletes=True,
        )

        # User memories for personalized AI responses
        memories = relationship(
            "UserMemory",
            back_populates="user",
            order_by="UserMemory.updated_at.desc()",
            cascade="all, delete-orphan",
        )

        # Incentive tasks completed by this user
        incentive_tasks = relationship(
            "UserIncentiveTask",
            back_populates="user",
            cascade="all, delete-orphan",
        )

        # Page usage tracking for ETL services
        pages_limit = Column(
            Integer,
            nullable=False,
            default=config.PAGES_LIMIT,
            server_default=str(config.PAGES_LIMIT),
        )
        pages_used = Column(Integer, nullable=False, default=0, server_default="0")

        # User profile (can be set manually for non-OAuth users)
        display_name = Column(String, nullable=True)
        avatar_url = Column(String, nullable=True)


engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def setup_indexes():
    async with engine.begin() as conn:
        # Create indexes
        # Document Summary Indexes
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS document_vector_index ON documents USING hnsw (embedding public.vector_cosine_ops)"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS document_search_index ON documents USING gin (to_tsvector('english', content))"
            )
        )
        # Document Chuck Indexes
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS chucks_vector_index ON chunks USING hnsw (embedding public.vector_cosine_ops)"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS chucks_search_index ON chunks USING gin (to_tsvector('english', content))"
            )
        )
        # pg_trgm indexes for efficient ILIKE '%term%' searches on titles
        # Critical for document mention picker (@mentions) to scale
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_documents_title_trgm ON documents USING gin (title gin_trgm_ops)"
            )
        )
        # B-tree index on search_space_id for fast filtering
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_documents_search_space_id ON documents (search_space_id)"
            )
        )
        # Covering index for "recent documents" query - enables index-only scan
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_documents_search_space_updated ON documents (search_space_id, updated_at DESC NULLS LAST) INCLUDE (id, title, document_type)"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_surfsense_docs_title_trgm ON surfsense_docs_documents USING gin (title gin_trgm_ops)"
            )
        )


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)
    await setup_indexes()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


if config.AUTH_TYPE == "GOOGLE":

    async def get_user_db(session: AsyncSession = Depends(get_async_session)):
        yield SQLAlchemyUserDatabase(session, User, OAuthAccount)

else:

    async def get_user_db(session: AsyncSession = Depends(get_async_session)):
        yield SQLAlchemyUserDatabase(session, User)


def has_permission(user_permissions: list[str], required_permission: str) -> bool:
    """
    Check if the user has the required permission.
    Supports wildcard (*) for full access.

    Args:
        user_permissions: List of permission strings the user has
        required_permission: The permission string to check for

    Returns:
        True if user has the permission, False otherwise
    """
    if not user_permissions:
        return False

    # Full access wildcard grants all permissions
    if Permission.FULL_ACCESS.value in user_permissions:
        return True

    return required_permission in user_permissions


def has_any_permission(
    user_permissions: list[str], required_permissions: list[str]
) -> bool:
    """
    Check if the user has any of the required permissions.

    Args:
        user_permissions: List of permission strings the user has
        required_permissions: List of permission strings to check for (any match)

    Returns:
        True if user has at least one of the permissions, False otherwise
    """
    if not user_permissions:
        return False

    if Permission.FULL_ACCESS.value in user_permissions:
        return True

    return any(perm in user_permissions for perm in required_permissions)


def has_all_permissions(
    user_permissions: list[str], required_permissions: list[str]
) -> bool:
    """
    Check if the user has all of the required permissions.

    Args:
        user_permissions: List of permission strings the user has
        required_permissions: List of permission strings to check for (all must match)

    Returns:
        True if user has all of the permissions, False otherwise
    """
    if not user_permissions:
        return False

    if Permission.FULL_ACCESS.value in user_permissions:
        return True

    return all(perm in user_permissions for perm in required_permissions)


def get_default_roles_config() -> list[dict]:
    """
    Get the configuration for default system roles.
    These roles are created automatically when a search space is created.

    Only 3 roles are supported:
    - Owner: Full access to everything (assigned to search space creator)
    - Editor: Can create/update content but cannot delete, manage roles, or change settings
    - Viewer: Read-only access to resources (can add comments)

    Returns:
        List of role configurations with name, description, permissions, and flags
    """
    return [
        {
            "name": "Owner",
            "description": "Full access to all search space resources and settings",
            "permissions": DEFAULT_ROLE_PERMISSIONS["Owner"],
            "is_default": False,
            "is_system_role": True,
        },
        {
            "name": "Editor",
            "description": "Can create and update content (no delete, role management, or settings access)",
            "permissions": DEFAULT_ROLE_PERMISSIONS["Editor"],
            "is_default": True,  # Default role for new members via invite
            "is_system_role": True,
        },
        {
            "name": "Viewer",
            "description": "Read-only access to search space resources",
            "permissions": DEFAULT_ROLE_PERMISSIONS["Viewer"],
            "is_default": False,
            "is_system_role": True,
        },
    ]
