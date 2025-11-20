from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from enum import Enum
import uuid

from fastapi import Depends
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable, SQLAlchemyUserDatabase
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    JSON,
    TIMESTAMP,
    BigInteger,
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, relationship

from app.config import config
from app.retriver.chunks_hybrid_search import ChucksHybridSearchRetriever
from app.retriver.documents_hybrid_search import DocumentHybridSearchRetriever

DATABASE_URL = config.DATABASE_URL


class DocumentType(str, Enum):
    EXTENSION = "EXTENSION"
    CRAWLED_URL = "CRAWLED_URL"
    FILE = "FILE"
    SLACK_CONNECTOR = "SLACK_CONNECTOR"
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
    AIRTABLE_CONNECTOR = "AIRTABLE_CONNECTOR"
    LUMA_CONNECTOR = "LUMA_CONNECTOR"
    ELASTICSEARCH_CONNECTOR = "ELASTICSEARCH_CONNECTOR"
    HOME_ASSISTANT_CONNECTOR = "HOME_ASSISTANT_CONNECTOR"
    MASTODON_CONNECTOR = "MASTODON_CONNECTOR"
    JELLYFIN_CONNECTOR = "JELLYFIN_CONNECTOR"
    RSS_FEED_CONNECTOR = "RSS_FEED_CONNECTOR"


class SearchSourceConnectorType(str, Enum):
    SERPER_API = "SERPER_API"
    TAVILY_API = "TAVILY_API"
    SEARXNG_API = "SEARXNG_API"
    LINKUP_API = "LINKUP_API"
    BAIDU_SEARCH_API = "BAIDU_SEARCH_API"
    SLACK_CONNECTOR = "SLACK_CONNECTOR"
    NOTION_CONNECTOR = "NOTION_CONNECTOR"
    GITHUB_CONNECTOR = "GITHUB_CONNECTOR"
    LINEAR_CONNECTOR = "LINEAR_CONNECTOR"
    DISCORD_CONNECTOR = "DISCORD_CONNECTOR"
    JIRA_CONNECTOR = "JIRA_CONNECTOR"
    CONFLUENCE_CONNECTOR = "CONFLUENCE_CONNECTOR"
    CLICKUP_CONNECTOR = "CLICKUP_CONNECTOR"
    GOOGLE_CALENDAR_CONNECTOR = "GOOGLE_CALENDAR_CONNECTOR"
    GOOGLE_GMAIL_CONNECTOR = "GOOGLE_GMAIL_CONNECTOR"
    AIRTABLE_CONNECTOR = "AIRTABLE_CONNECTOR"
    LUMA_CONNECTOR = "LUMA_CONNECTOR"
    ELASTICSEARCH_CONNECTOR = "ELASTICSEARCH_CONNECTOR"
    HOME_ASSISTANT_CONNECTOR = "HOME_ASSISTANT_CONNECTOR"
    MASTODON_CONNECTOR = "MASTODON_CONNECTOR"
    JELLYFIN_CONNECTOR = "JELLYFIN_CONNECTOR"
    RSS_FEED_CONNECTOR = "RSS_FEED_CONNECTOR"


class ChatType(str, Enum):
    QNA = "QNA"


class LiteLLMProvider(str, Enum):
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


class SocialMediaPlatform(str, Enum):
    MASTODON = "MASTODON"
    PIXELFED = "PIXELFED"
    BOOKWYRM = "BOOKWYRM"
    LEMMY = "LEMMY"
    PEERTUBE = "PEERTUBE"
    GITHUB = "GITHUB"
    GITLAB = "GITLAB"
    MATRIX = "MATRIX"
    LINKEDIN = "LINKEDIN"
    WEBSITE = "WEBSITE"
    EMAIL = "EMAIL"
    OTHER = "OTHER"


class SecurityEventType(str, Enum):
    """Security-related event types for audit logging."""
    TWO_FA_ENABLED = "TWO_FA_ENABLED"
    TWO_FA_DISABLED = "TWO_FA_DISABLED"
    TWO_FA_SETUP_INITIATED = "TWO_FA_SETUP_INITIATED"
    TWO_FA_VERIFICATION_SUCCESS = "TWO_FA_VERIFICATION_SUCCESS"
    TWO_FA_VERIFICATION_FAILED = "TWO_FA_VERIFICATION_FAILED"
    TWO_FA_LOGIN_SUCCESS = "TWO_FA_LOGIN_SUCCESS"
    TWO_FA_LOGIN_FAILED = "TWO_FA_LOGIN_FAILED"
    BACKUP_CODE_USED = "BACKUP_CODE_USED"
    BACKUP_CODES_REGENERATED = "BACKUP_CODES_REGENERATED"
    PASSWORD_LOGIN_SUCCESS = "PASSWORD_LOGIN_SUCCESS"
    PASSWORD_LOGIN_FAILED = "PASSWORD_LOGIN_FAILED"


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    @declared_attr
    def created_at(cls):
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


class Chat(BaseModel, TimestampMixin):
    __tablename__ = "chats"

    type = Column(SQLAlchemyEnum(ChatType), nullable=False)
    title = Column(String, nullable=False, index=True)
    initial_connectors = Column(ARRAY(String), nullable=True)
    messages = Column(JSON, nullable=False)
    state_version = Column(BigInteger, nullable=False, default=1)

    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )
    search_space = relationship("SearchSpace", back_populates="chats")


class Document(BaseModel, TimestampMixin):
    __tablename__ = "documents"

    title = Column(String, nullable=False, index=True)
    document_type = Column(SQLAlchemyEnum(DocumentType), nullable=False)
    document_metadata = Column(JSON, nullable=True)

    content = Column(Text, nullable=False)
    content_hash = Column(String, nullable=False, index=True, unique=True)
    unique_identifier_hash = Column(String, nullable=True, index=True, unique=True)
    embedding = Column(Vector(config.embedding_model_instance.dimension))

    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )
    search_space = relationship("SearchSpace", back_populates="documents")
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


class Podcast(BaseModel, TimestampMixin):
    __tablename__ = "podcasts"

    title = Column(String, nullable=False, index=True)
    podcast_transcript = Column(JSON, nullable=False, default={})
    file_location = Column(String(500), nullable=False, default="")
    chat_id = Column(
        Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=True
    )
    chat_state_version = Column(BigInteger, nullable=True)

    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )
    search_space = relationship("SearchSpace", back_populates="podcasts")


class SearchSpace(BaseModel, TimestampMixin):
    __tablename__ = "searchspaces"

    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)

    citations_enabled = Column(
        Boolean, nullable=False, default=True
    )  # Enable/disable citations
    qna_custom_instructions = Column(
        Text, nullable=True
    )  # User's custom instructions
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
    podcasts = relationship(
        "Podcast",
        back_populates="search_space",
        order_by="Podcast.id",
        cascade="all, delete-orphan",
    )
    chats = relationship(
        "Chat",
        back_populates="search_space",
        order_by="Chat.id",
        cascade="all, delete-orphan",
    )
    logs = relationship(
        "Log",
        back_populates="search_space",
        order_by="Log.id",
        cascade="all, delete-orphan",
    )
    search_source_connectors = relationship(
        "SearchSourceConnector",
        back_populates="search_space",
        order_by="SearchSourceConnector.id",
        cascade="all, delete-orphan",
    )
    llm_configs = relationship(
        "LLMConfig",
        back_populates="search_space",
        order_by="LLMConfig.id",
        cascade="all, delete-orphan",
    )
    user_preferences = relationship(
        "UserSearchSpacePreference",
        back_populates="search_space",
        cascade="all, delete-orphan",
    )


class SearchSourceConnector(BaseModel, TimestampMixin):
    __tablename__ = "search_source_connectors"
    __table_args__ = (
        UniqueConstraint(
            "search_space_id",
            "user_id",
            "connector_type",
            name="uq_searchspace_user_connector_type",
        ),
    )

    name = Column(String(100), nullable=False, index=True)
    connector_type = Column(SQLAlchemyEnum(SearchSourceConnectorType), nullable=False)
    is_indexable = Column(Boolean, nullable=False, default=False)
    last_indexed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    config = Column(JSON, nullable=False)

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


class LLMConfig(BaseModel, TimestampMixin):
    __tablename__ = "llm_configs"

    name = Column(String(100), nullable=False, index=True)
    provider = Column(SQLAlchemyEnum(LiteLLMProvider), nullable=False)
    custom_provider = Column(String(100), nullable=True)
    model_name = Column(String(100), nullable=False)
    api_key = Column(String, nullable=False)
    api_base = Column(String(500), nullable=True)

    language = Column(String(50), nullable=True, default="English")

    litellm_params = Column(JSON, nullable=True, default={})

    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )
    search_space = relationship("SearchSpace", back_populates="llm_configs")


class UserSearchSpacePreference(BaseModel, TimestampMixin):
    __tablename__ = "user_search_space_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "search_space_id",
            name="uq_user_searchspace",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )

    long_context_llm_id = Column(Integer, nullable=True)
    fast_llm_id = Column(Integer, nullable=True)
    strategic_llm_id = Column(Integer, nullable=True)

    user = relationship("User", back_populates="search_space_preferences")
    search_space = relationship("SearchSpace", back_populates="user_preferences")


class Log(BaseModel, TimestampMixin):
    __tablename__ = "logs"

    level = Column(SQLAlchemyEnum(LogLevel), nullable=False, index=True)
    status = Column(SQLAlchemyEnum(LogStatus), nullable=False, index=True)
    message = Column(Text, nullable=False)
    source = Column(String(200), nullable=True, index=True)
    log_metadata = Column(JSON, nullable=True, default={})

    search_space_id = Column(
        Integer, ForeignKey("searchspaces.id", ondelete="CASCADE"), nullable=False
    )
    search_space = relationship("SearchSpace", back_populates="logs")


class SecurityEvent(BaseModel, TimestampMixin):
    """Security audit log for tracking security-related events."""
    __tablename__ = "security_events"

    event_type = Column(SQLAlchemyEnum(SecurityEventType), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 max length is 45
    user_agent = Column(String(500), nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    details = Column(JSON, nullable=True, default=dict)

    user = relationship("User", backref="security_events")


class SocialMediaLink(BaseModel, TimestampMixin):
    __tablename__ = "social_media_links"

    platform = Column(SQLAlchemyEnum(SocialMediaPlatform), nullable=False, index=True)
    url = Column(String(500), nullable=False)
    label = Column(String(100), nullable=True)  # Optional custom label
    display_order = Column(Integer, nullable=False, default=0)  # For ordering links
    is_active = Column(Boolean, nullable=False, default=True)  # Toggle visibility


class SiteConfiguration(Base):
    __tablename__ = "site_configuration"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)

    # Header/Navbar toggles
    show_pricing_link = Column(Boolean, nullable=False, default=False)
    show_docs_link = Column(Boolean, nullable=False, default=False)
    show_github_link = Column(Boolean, nullable=False, default=False)
    show_sign_in = Column(Boolean, nullable=False, default=True)

    # Homepage toggles
    show_get_started_button = Column(Boolean, nullable=False, default=False)
    show_talk_to_us_button = Column(Boolean, nullable=False, default=False)

    # Footer toggles
    show_pages_section = Column(Boolean, nullable=False, default=False)
    show_legal_section = Column(Boolean, nullable=False, default=False)
    show_register_section = Column(Boolean, nullable=False, default=False)

    # Route disabling
    disable_pricing_route = Column(Boolean, nullable=False, default=True)
    disable_docs_route = Column(Boolean, nullable=False, default=True)
    disable_contact_route = Column(Boolean, nullable=False, default=True)
    disable_terms_route = Column(Boolean, nullable=False, default=True)
    disable_privacy_route = Column(Boolean, nullable=False, default=True)

    # Registration control
    disable_registration = Column(Boolean, nullable=False, default=False)

    # Contact information
    show_contact_email = Column(Boolean, nullable=False, default=True)
    contact_email = Column(String(200), nullable=True, default=config.DEFAULT_CONTACT_EMAIL)

    # Custom text
    custom_copyright = Column(String(200), nullable=True, default="SurfSense 2025")


if config.AUTH_TYPE == "GOOGLE":

    class OAuthAccount(Base):
        __tablename__ = "oauth_account"
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    class User(SQLAlchemyBaseUserTable, Base):
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        oauth_accounts = relationship("OAuthAccount", lazy="joined")
        search_spaces = relationship("SearchSpace", back_populates="user")
        search_space_preferences = relationship(
            "UserSearchSpacePreference", back_populates="user", cascade="all, delete-orphan"
        )
        pages_limit = Column(Integer, nullable=False, default=1000, server_default="1000")
        pages_used = Column(Integer, nullable=False, default=0, server_default="0")
        # Two-factor authentication fields
        two_fa_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
        totp_secret = Column(String(255), nullable=True)
        backup_codes = Column(JSON, nullable=True)

else:

    class User(SQLAlchemyBaseUserTable, Base):
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        search_spaces = relationship("SearchSpace", back_populates="user")
        search_space_preferences = relationship(
            "UserSearchSpacePreference", back_populates="user", cascade="all, delete-orphan"
        )
        pages_limit = Column(Integer, nullable=False, default=1000, server_default="1000")
        pages_used = Column(Integer, nullable=False, default=0, server_default="0")
        # Two-factor authentication fields
        two_fa_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
        totp_secret = Column(String(255), nullable=True)
        backup_codes = Column(JSON, nullable=True)


engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def setup_indexes():
    async with engine.begin() as conn:
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


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
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


async def get_chucks_hybrid_search_retriever(
    session: AsyncSession = Depends(get_async_session),
):
    return ChucksHybridSearchRetriever(session)


async def get_documents_hybrid_search_retriever(
    session: AsyncSession = Depends(get_async_session),
):
    return DocumentHybridSearchRetriever(session)

