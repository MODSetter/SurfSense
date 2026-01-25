<a href="https://www.surfsense.com/"><img width="1584" height="396" alt="readme_banner" src="https://github.com/user-attachments/assets/9361ef58-1753-4b6e-b275-5020d8847261" /></a>



<div align="center">
<a href="https://discord.gg/ejRNvftDp9">
<img src="https://img.shields.io/discord/1359368468260192417" alt="Discord">
</a>
<a href="https://www.reddit.com/r/SurfSense/">
<img src="https://img.shields.io/reddit/subreddit-subscribers/SurfSense?style=social" alt="Reddit">
</a>
</div>

<div align="center">

[English](README.md) | [简体中文](README.zh-CN.md)

</div>

# SurfSense
Connect any LLM to your internal knowledge sources and chat with it in real time alongside your team. OSS alternative to NotebookLM, Perplexity, and Glean.

SurfSense is a highly customizable AI research agent, connected to external sources such as Search Engines (SearxNG, Tavily, LinkUp), Google Drive, Slack, Microsoft Teams, Linear, Jira, ClickUp, Confluence, BookStack, Gmail, Notion, YouTube, GitHub, Discord, Airtable, Google Calendar, Luma, Circleback, Elasticsearch, Obsidian and more to come.

<div align="center">
<a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter%2FSurfSense | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>


# Video 

https://github.com/user-attachments/assets/cc0c84d3-1f2f-4f7a-b519-2ecce22310b1


## Podcast Sample

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7




## Key Features

### 💡 **Idea**: 
- Open source alternative to NotebookLM, Perplexity, and Glean. Connect any LLM to your internal knowledge sources and collaborate with your team in real time.
### 📁 **Multiple File Format Uploading Support**
- Save content from your own personal files *(Documents, images, videos and supports **50+ file extensions**)* to your own personal knowledge base .
### 🔍 **Powerful Search**
- Quickly research or find anything in your saved content .
### 💬 **Chat with your Saved Content**
- Interact in Natural Language and get cited answers.
### 📄 **Cited Answers**
- Get Cited answers just like Perplexity.
### 🧩 **Universal Compatibility**
- Connect virtually any inference provider via the OpenAI spec and LiteLLM.
### 🔔 **Privacy & Local LLM Support**
- Works Flawlessly with local LLMs like vLLM and Ollama.
### 🏠 **Self Hostable**
- Open source and easy to deploy locally.
### 👥 **Team Collaboration with RBAC**
- Role-Based Access Control for Search Spaces
- Invite team members with customizable roles (Owner, Admin, Editor, Viewer)
- Granular permissions for documents, chats, connectors, and settings
- Share knowledge bases securely within your organization
- Team chats update in real-time and "Chat about the chat" in comment threads
### 🎙️ Podcasts 
- Blazingly fast podcast generation agent. (Creates a 3-minute podcast in under 20 seconds.)
- Convert your chat conversations into engaging audio content
- Support for local TTS providers (Kokoro TTS)
- Support for multiple TTS providers (OpenAI, Azure, Google Vertex AI)

### 🤖 **Deep Agent Architecture**
- Powered by [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) - agents that can plan, use subagents, and leverage file systems for complex tasks.

### 📊 **Advanced RAG Techniques**
- Supports 100+ LLM's
- Supports 6000+ Embedding Models.
- Supports all major Rerankers (Pinecone, Cohere, Flashrank etc)
- Uses Hierarchical Indices (2 tiered RAG setup).
- Utilizes Hybrid Search (Semantic + Full Text Search combined with Reciprocal Rank Fusion).

### ℹ️ **External Sources**
- Search Engines (Tavily, LinkUp)
- SearxNG (self-hosted instances)
- Google Drive
- Slack
- Microsoft Teams
- Linear
- Jira
- ClickUp
- Confluence
- BookStack
- Notion
- Gmail
- Youtube Videos
- GitHub
- Discord
- Airtable
- Google Calendar
- Luma
- Circleback
- Elasticsearch
- Obsidian
- and more to come.....

## 📄 **Supported File Extensions**

| ETL Service | Formats | Notes |
|-------------|---------|-------|
| **LlamaCloud** | 50+ formats | Documents, presentations, spreadsheets, images |
| **Unstructured** | 34+ formats | Core formats + email support |
| **Docling** | Core formats | Local processing, no API key required |

**Audio/Video** (via STT Service): `.mp3`, `.wav`, `.mp4`, `.webm`, etc.

### 🔖 Cross Browser Extension
- The SurfSense extension can be used to save any webpage you like.
- Its main usecase is to save any webpages protected beyond authentication.



## FEATURE REQUESTS AND FUTURE


**SurfSense is actively being developed.** While it's not yet production-ready, you can help us speed up the process.

Join the [SurfSense Discord](https://discord.gg/ejRNvftDp9) and help shape the future of SurfSense!

## 🚀 Roadmap

Stay up to date with our development progress and upcoming features!  
Check out our public roadmap and contribute your ideas or feedback:

**📋 Roadmap Discussion:** [SurfSense 2025-2026 Roadmap: Deep Agents, Real-Time Collaboration & MCP Servers](https://github.com/MODSetter/SurfSense/discussions/565)

**📊 Kanban Board:** [SurfSense Project Board](https://github.com/users/MODSetter/projects/3)


## How to get started?

### Quick Start with Docker 🐳

> [!TIP]
> For production deployments, use the full [Docker Compose setup](https://www.surfsense.com/docs/docker-installation) which offers more control and scalability.

**Linux/macOS:**

```bash
docker run -d -p 3000:3000 -p 8000:8000 -p 5133:5133 \
  -v surfsense-data:/data \
  --name surfsense \
  --restart unless-stopped \
  ghcr.io/modsetter/surfsense:latest
```

**Windows (PowerShell):**

```powershell
docker run -d -p 3000:3000 -p 8000:8000 -p 5133:5133 `
  -v surfsense-data:/data `
  --name surfsense `
  --restart unless-stopped `
  ghcr.io/modsetter/surfsense:latest
```

**With Custom Configuration:**

You can pass any environment variable using `-e` flags:

```bash
docker run -d -p 3000:3000 -p 8000:8000 -p 5133:5133 \
  -v surfsense-data:/data \
  -e EMBEDDING_MODEL=openai://text-embedding-ada-002 \
  -e OPENAI_API_KEY=your_openai_api_key \
  -e AUTH_TYPE=GOOGLE \
  -e GOOGLE_OAUTH_CLIENT_ID=your_google_client_id \
  -e GOOGLE_OAUTH_CLIENT_SECRET=your_google_client_secret \
  -e ETL_SERVICE=LLAMACLOUD \
  -e LLAMA_CLOUD_API_KEY=your_llama_cloud_key \
  --name surfsense \
  --restart unless-stopped \
  ghcr.io/modsetter/surfsense:latest
```

> [!NOTE]
> - If deploying behind a reverse proxy with HTTPS, add `-e BACKEND_URL=https://api.yourdomain.com`

After starting, access SurfSense at:
- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Electric-SQL**: [http://localhost:5133](http://localhost:5133)

**Useful Commands:**

```bash
docker logs -f surfsense      # View logs
docker stop surfsense         # Stop
docker start surfsense        # Start
docker rm surfsense           # Remove (data preserved in volume)
```

### Installation Options

SurfSense provides multiple options to get started:

1. **[SurfSense Cloud](https://www.surfsense.com/login)** - The easiest way to try SurfSense without any setup.
   - No installation required
   - Instant access to all features
   - Perfect for getting started quickly

2. **Quick Start Docker (Above)** - Single command to get SurfSense running locally.
   - All-in-one image with PostgreSQL, Redis, and all services bundled
   - Perfect for evaluation, development, and small deployments
   - Data persisted via Docker volume

3. **[Docker Compose (Production)](https://www.surfsense.com/docs/docker-installation)** - Full stack deployment with separate services.
   - Includes pgAdmin for database management through a web UI
   - Supports environment variable customization via `.env` file
   - Flexible deployment options (full stack or core services only)
   - Better for production with separate scaling of services

4. **[Manual Installation](https://www.surfsense.com/docs/manual-installation)** - For users who prefer more control over their setup or need to customize their deployment.

Docker and manual installation guides include detailed OS-specific instructions for Windows, macOS, and Linux.

Before self-hosting installation, make sure to complete the [prerequisite setup steps](https://www.surfsense.com/docs/) including:
- Auth setup (optional - defaults to LOCAL auth)
- **File Processing ETL Service** (optional - defaults to Docling):
  - Docling (default, local processing, no API key required, supports PDF, Office docs, images, HTML, CSV)
  - Unstructured.io API key (supports 34+ formats)
  - LlamaIndex API key (enhanced parsing, supports 50+ formats)
- Other API keys as needed for your use case



## Tech Stack


 ### **BackEnd** 

-  **LiteLLM**: Universal LLM integration supporting 100+ models (OpenAI, Anthropic, Ollama, etc.)

-  **FastAPI**: Modern, fast web framework for building APIs with Python
  
-  **PostgreSQL with pgvector**: Database with vector search capabilities for similarity searches

-  **SQLAlchemy**: SQL toolkit and ORM (Object-Relational Mapping) for database interactions

-  **Alembic**: A database migrations tool for SQLAlchemy.

-  **FastAPI Users**: Authentication and user management with JWT and OAuth support

-  **Deep Agents**: Custom agent framework built on LangGraph for reasoning and acting AI agents with configurable tools

-  **LangGraph**: Framework for developing stateful AI agents with conversation persistence

-  **LangChain**: Framework for developing AI-powered applications.

-  **Rerankers**: Advanced result ranking for improved search relevance

-  **Hybrid Search**: Combines vector similarity and full-text search for optimal results using Reciprocal Rank Fusion (RRF)

-  **Vector Embeddings**: Document and text embeddings for semantic search

-  **pgvector**: PostgreSQL extension for efficient vector similarity operations

-  **Redis**: In-memory data structure store used as message broker and result backend for Celery

-  **Celery**: Distributed task queue for handling asynchronous background jobs (document processing, podcast generation, etc.)

-  **Flower**: Real-time monitoring and administration tool for Celery task queues

-  **Chonkie**: Advanced document chunking and embedding library

  
---
 ### **FrontEnd**

-  **Next.js**: React framework featuring App Router, server components, automatic code-splitting, and optimized rendering.

-  **React**: JavaScript library for building user interfaces.

-  **TypeScript**: Static type-checking for JavaScript, enhancing code quality and developer experience.

- **Vercel AI SDK Kit UI Stream Protocol**: To create scalable chat UI.

-  **Tailwind CSS**: Utility-first CSS framework for building custom UI designs.

-  **Shadcn**: Headless components library.

-  **Motion (Framer Motion)**: Animation library for React.



 ### **DevOps**

-  **Docker**: Container platform for consistent deployment across environments
  
-  **Docker Compose**: Tool for defining and running multi-container Docker applications

-  **pgAdmin**: Web-based PostgreSQL administration tool included in Docker setup


### **Extension** 
 Manifest v3 on Plasmo


## Contribute 

Contributions are very welcome! A contribution can be as small as a ⭐ or even finding and creating issues.
Fine-tuning the Backend is always desired.

### Adding New Agent Tools

Want to add a new tool to the SurfSense agent? It's easy:

1. Create your tool file in `surfsense_backend/app/agents/new_chat/tools/my_tool.py`
2. Register it in `registry.py`:

```python
ToolDefinition(
    name="my_tool",
    description="What my tool does",
    factory=lambda deps: create_my_tool(
        search_space_id=deps["search_space_id"],
        db_session=deps["db_session"],
    ),
    requires=["search_space_id", "db_session"],
),
```

For detailed contribution guidelines, please see our [CONTRIBUTING.md](CONTRIBUTING.md) file.

## Star History

<a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
 </picture>
</a>

---
---
<p align="center">
    <img 
      src="https://github.com/user-attachments/assets/329c9bc2-6005-4aed-a629-700b5ae296b4" 
      alt="Catalyst Project" 
      width="200"
    />
</p>

---
---
