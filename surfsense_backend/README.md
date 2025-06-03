# Surf Backend

## Technology Stack Overview

This application is a modern AI-powered search and knowledge management platform built with the following technology stack:

### Core Framework and Environment
- **Python 3.12+**: The application requires Python 3.12 or newer
- **FastAPI**: Modern, fast web framework for building APIs with Python
- **Uvicorn**: ASGI server implementation, running the FastAPI application
- **PostgreSQL with pgvector**: Database with vector search capabilities for similarity searches
- **SQLAlchemy**: SQL toolkit and ORM (Object-Relational Mapping) for database interactions
- **FastAPI Users**: Authentication and user management with JWT and OAuth support

### Key Features and Components

#### Authentication and User Management
- JWT-based authentication
- OAuth integration (Google)
- User registration, login, and password reset flows

#### Search and Retrieval System
- **Hybrid Search**: Combines vector similarity and full-text search for optimal results using Reciprocal Rank Fusion (RRF)
- **Vector Embeddings**: Document and text embeddings for semantic search
- **pgvector**: PostgreSQL extension for efficient vector similarity operations
- **Chonkie**: Advanced document chunking and embedding library
  - Uses `AutoEmbeddings` for flexible embedding model selection
  - `LateChunker` for optimized document chunking based on embedding model's max sequence length

#### AI and NLP Capabilities
- **LangChain**: Framework for developing AI-powered applications
  - Used for document processing, research, and response generation
  - Integration with various LLM models through LiteLLM
  - Document conversion utilities for standardized processing
- **GPT Integration**: Integration with LLM models through LiteLLM
  - Multiple LLM configurations for different use cases:
    - Fast LLM: Quick responses (default: gpt-4o-mini)
    - Smart LLM: More comprehensive analysis (default: gpt-4o-mini)
    - Strategic LLM: Complex reasoning (default: gpt-4o-mini)
    - Long Context LLM: For processing large documents (default: gemini-2.0-flash-thinking)
- **Rerankers with FlashRank**: Advanced result ranking for improved search relevance
  - Configurable reranking models (default: ms-marco-MiniLM-L-12-v2)
  - Supports multiple reranking backends (FlashRank, Cohere, etc.)
  - Improves search result quality by reordering based on semantic relevance
- **GPT-Researcher**: Advanced research capabilities
  - Multiple research modes (GENERAL, DEEP, DEEPER)
  - Customizable report formats with proper citations
  - Streaming research results for real-time updates

#### External Integrations
- **Slack Connector**: Integration with Slack for data retrieval and notifications
- **Notion Connector**: Integration with Notion for document retrieval
- **Search APIs**: Integration with Tavily and Serper API for web search
- **Firecrawl**: Web crawling and data extraction capabilities

#### Data Processing
- **Unstructured**: Tools for processing unstructured data
- **Markdownify**: Converting HTML to Markdown
- **Playwright**: Web automation and scraping capabilities

#### Main Modules
- **Search Spaces**: Isolated search environments for different contexts or projects
- **Documents**: Storage and retrieval of various document types
- **Chunks**: Document fragments for more precise retrieval
- **Chats**: Conversation management with different depth levels (GENERAL, DEEP)
- **Podcasts**: Audio content management with generation capabilities
- **Search Source Connectors**: Integration with various data sources

### Development Tools
- **Poetry**: Python dependency management (indicated by pyproject.toml)
- **CORS support**: Cross-Origin Resource Sharing enabled for API access
- **Environment Variables**: Configuration through .env files

## Database Schema

The application uses a relational database with the following main entities:
- Users: Authentication and user management
- SearchSpaces: Isolated search environments owned by users
- Documents: Various document types with content and embeddings
- Chunks: Smaller pieces of documents for granular retrieval
- Chats: Conversation tracking with different depth levels
- Podcasts: Audio content with generation capabilities
- SearchSourceConnectors: External data source integrations

## API Endpoints

The API is structured with the following main route groups:
- `/auth/*`: Authentication endpoints (JWT, OAuth)
- `/users/*`: User management
- `/api/v1/search-spaces/*`: Search space management
- `/api/v1/documents/*`: Document management
- `/api/v1/podcasts/*`: Podcast functionality
- `/api/v1/chats/*`: Chat and conversation endpoints
- `/api/v1/search-source-connectors/*`: External data source management

## Deployment

The application is configured to run with Uvicorn and can be deployed with:
```
python main.py
```

This will start the server on all interfaces (0.0.0.0) with info-level logging.

## Requirements

See pyproject.toml for detailed dependency information. Key dependencies include:
- asyncpg: Asynchronous PostgreSQL client
- chonkie: Document chunking and embedding library
- fastapi and related packages
- fastapi-users: Authentication and user management
- firecrawl-py: Web crawling capabilities
- langchain components for AI workflows
- litellm: LLM model integration
- pgvector: Vector similarity search in PostgreSQL
- rerankers with FlashRank: Advanced result ranking
- Various AI and NLP libraries
- Integration clients for Slack, Notion, etc.
