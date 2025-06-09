
![new_header](https://github.com/user-attachments/assets/e236b764-0ddc-42ff-a1f1-8fbb3d2e0e65)


<div align="center">
<a href="https://discord.gg/ejRNvftDp9">
<img src="https://img.shields.io/discord/1359368468260192417" alt="Discord">
</a>
</div>


# SurfSense
While tools like NotebookLM and Perplexity are impressive and highly effective for conducting research on any topic/query, SurfSense elevates this capability by integrating with your personal knowledge base. It is a highly customizable AI research agent, connected to external sources such as search engines (Tavily, LinkUp), Slack, Linear, Notion, YouTube, GitHub, Discord and more to come.

<div align="center">
<a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter%2FSurfSense | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>


# Video 
## Old video. New one coming soon.
https://github.com/user-attachments/assets/48142909-6391-4084-b7e8-81da388bb1fc

# Podcast's

https://github.com/user-attachments/assets/d516982f-de00-4c41-9e4c-632a7d942f41

## Podcast Sample

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7




## Key Features

### 💡 **Idea**: 
Have your own highly customizable private NotebookLM and Perplexity integrated with external sources.
### 📁 **Multiple File Format Uploading Support**
Save content from your own personal files *(Documents, images, videos and supports **50+ file extensions**)* to your own personal knowledge base .
### 🔍 **Powerful Search**
Quickly research or find anything in your saved content .
### 💬 **Chat with your Saved Content**
 Interact in Natural Language and get cited answers.
### 📄 **Cited Answers**
Get Cited answers just like Perplexity.
### 🔔 **Privacy & Local LLM Support**
Works Flawlessly with Ollama local LLMs.
### 🏠 **Self Hostable**
Open source and easy to deploy locally.
### 🎙️ Podcasts 
- Blazingly fast podcast generation agent. (Creates a 3-minute podcast in under 20 seconds.)
- Convert your chat conversations into engaging audio content
- Support for multiple TTS providers (OpenAI, Azure, Google Vertex AI)

### 📊 **Advanced RAG Techniques**
- Supports 100+ LLM's
- Supports 6000+ Embedding Models.
- Supports all major Rerankers (Pinecode, Cohere, Flashrank etc)
- Uses Hierarchical Indices (2 tiered RAG setup).
- Utilizes Hybrid Search (Semantic + Full Text Search combined with Reciprocal Rank Fusion).
- RAG as a Service API Backend.

### ℹ️ **External Sources**
- Search Engines (Tavily, LinkUp)
- Slack
- Linear
- Notion
- Youtube Videos
- GitHub
- Discord
- and more to come.....

## 📄 **Supported File Extensions**

> **Note**: File format support depends on your ETL service configuration. LlamaCloud supports 50+ formats, while Unstructured supports 34+ core formats.

### Documents & Text
**LlamaCloud**: `.pdf`, `.doc`, `.docx`, `.docm`, `.dot`, `.dotm`, `.rtf`, `.txt`, `.xml`, `.epub`, `.odt`, `.wpd`, `.pages`, `.key`, `.numbers`, `.602`, `.abw`, `.cgm`, `.cwk`, `.hwp`, `.lwp`, `.mw`, `.mcw`, `.pbd`, `.sda`, `.sdd`, `.sdp`, `.sdw`, `.sgl`, `.sti`, `.sxi`, `.sxw`, `.stw`, `.sxg`, `.uof`, `.uop`, `.uot`, `.vor`, `.wps`, `.zabw`

**Unstructured**: `.doc`, `.docx`, `.odt`, `.rtf`, `.pdf`, `.xml`, `.txt`, `.md`, `.markdown`, `.rst`, `.html`, `.org`, `.epub`

### Presentations
**LlamaCloud**: `.ppt`, `.pptx`, `.pptm`, `.pot`, `.potm`, `.potx`, `.odp`, `.key`

**Unstructured**: `.ppt`, `.pptx`

### Spreadsheets & Data
**LlamaCloud**: `.xlsx`, `.xls`, `.xlsm`, `.xlsb`, `.xlw`, `.csv`, `.tsv`, `.ods`, `.fods`, `.numbers`, `.dbf`, `.123`, `.dif`, `.sylk`, `.slk`, `.prn`, `.et`, `.uos1`, `.uos2`, `.wk1`, `.wk2`, `.wk3`, `.wk4`, `.wks`, `.wq1`, `.wq2`, `.wb1`, `.wb2`, `.wb3`, `.qpw`, `.xlr`, `.eth`

**Unstructured**: `.xls`, `.xlsx`, `.csv`, `.tsv`

### Images
**LlamaCloud**: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.svg`, `.tiff`, `.webp`, `.html`, `.htm`, `.web`

**Unstructured**: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.heic`

### Audio & Video *(Always Supported)*
`.mp3`, `.mpga`, `.m4a`, `.wav`, `.mp4`, `.mpeg`, `.webm`

### Email & Communication
**Unstructured**: `.eml`, `.msg`, `.p7s`

### 🔖 Cross Browser Extension
- The SurfSense extension can be used to save any webpage you like.
- Its main usecase is to save any webpages protected beyond authentication.


## FEATURE REQUESTS AND FUTURE


**SurfSense is actively being developed.** While it's not yet production-ready, you can help us speed up the process.

Join the [SurfSense Discord](https://discord.gg/ejRNvftDp9) and help shape the future of SurfSense!

## 🚀 Roadmap

Stay up to date with our development progress and upcoming features!  
Check out our public roadmap and contribute your ideas or feedback:

**View the Roadmap:** [SurfSense Roadmap on GitHub Projects](https://github.com/users/MODSetter/projects/2)

## How to get started?

### Installation Options

SurfSense provides two installation methods:

1. **[Docker Installation](https://www.surfsense.net/docs/docker-installation)** - The easiest way to get SurfSense up and running with all dependencies containerized.
   - Includes pgAdmin for database management through a web UI
   - Supports environment variable customization via `.env` file
   - Flexible deployment options (full stack or core services only)
   - No need to manually edit configuration files between environments
   - See [Docker Setup Guide](DOCKER_SETUP.md) for detailed instructions
   - For deployment scenarios and options, see [Deployment Guide](DEPLOYMENT_GUIDE.md)

2. **[Manual Installation (Recommended)](https://www.surfsense.net/docs/manual-installation)** - For users who prefer more control over their setup or need to customize their deployment.

Both installation guides include detailed OS-specific instructions for Windows, macOS, and Linux.

Before installation, make sure to complete the [prerequisite setup steps](https://www.surfsense.net/docs/) including:
- PGVector setup
- **File Processing ETL Service** (choose one):
  - Unstructured.io API key (supports 34+ formats)
  - LlamaIndex API key (enhanced parsing, supports 50+ formats)
- Other required API keys

## Screenshots

**Research Agent** 

![updated_researcher](https://github.com/user-attachments/assets/e22c5d86-f511-4c72-8c50-feba0c1561b4)

**Search Spaces** 

![search_spaces](https://github.com/user-attachments/assets/e254c38c-f937-44b6-9e9d-770db583d099)

**Manage Documents** 
![documents](https://github.com/user-attachments/assets/7001e306-eb06-4009-89c6-8fadfdc3fc4d)

**Podcast Agent** 
![podcasts](https://github.com/user-attachments/assets/6cb82ffd-9e14-4172-bc79-67faf34c4c1c)


**Agent Chat** 

![git_chat](https://github.com/user-attachments/assets/bb352d52-1c6d-4020-926b-722d0b98b491)

**Browser Extension**

![ext1](https://github.com/user-attachments/assets/1f042b7a-6349-422b-94fb-d40d0df16c40)

![ext2](https://github.com/user-attachments/assets/a9b9f1aa-2677-404d-b0a0-c1b2dddf24a7)


## Tech Stack


 ### **BackEnd** 

-  **FastAPI**: Modern, fast web framework for building APIs with Python
  
-  **PostgreSQL with pgvector**: Database with vector search capabilities for similarity searches

-  **SQLAlchemy**: SQL toolkit and ORM (Object-Relational Mapping) for database interactions

-  **Alembic**: A database migrations tool for SQLAlchemy.

-  **FastAPI Users**: Authentication and user management with JWT and OAuth support

-  **LangGraph**: Framework for developing AI-agents.
  
-  **LangChain**: Framework for developing AI-powered applications.

-  **LLM Integration**: Integration with LLM models through LiteLLM

-  **Rerankers**: Advanced result ranking for improved search relevance

-  **Hybrid Search**: Combines vector similarity and full-text search for optimal results using Reciprocal Rank Fusion (RRF)

-  **Vector Embeddings**: Document and text embeddings for semantic search

-  **pgvector**: PostgreSQL extension for efficient vector similarity operations

-  **Chonkie**: Advanced document chunking and embedding library
 - Uses `AutoEmbeddings` for flexible embedding model selection
 -  `LateChunker` for optimized document chunking based on embedding model's max sequence length


  
---
 ### **FrontEnd**

-  **Next.js 15.2.3**: React framework featuring App Router, server components, automatic code-splitting, and optimized rendering.

-  **React 19.0.0**: JavaScript library for building user interfaces.

-  **TypeScript**: Static type-checking for JavaScript, enhancing code quality and developer experience.
- **Vercel AI SDK Kit UI Stream Protocol**: To create scalable chat UI.

-  **Tailwind CSS 4.x**: Utility-first CSS framework for building custom UI designs.

-  **Shadcn**: Headless components library.

-  **Lucide React**: Icon set implemented as React components.

-  **Framer Motion**: Animation library for React.

-  **Sonner**: Toast notification library.

-  **Geist**: Font family from Vercel.

-  **React Hook Form**: Form state management and validation.

-  **Zod**: TypeScript-first schema validation with static type inference.

-  **@hookform/resolvers**: Resolvers for using validation libraries with React Hook Form.

-  **@tanstack/react-table**: Headless UI for building powerful tables & datagrids.


 ### **DevOps**

-  **Docker**: Container platform for consistent deployment across environments
  
-  **Docker Compose**: Tool for defining and running multi-container Docker applications

-  **pgAdmin**: Web-based PostgreSQL administration tool included in Docker setup


### **Extension** 
 Manifest v3 on Plasmo

## Future Work
- Add More Connectors.
- Patch minor bugs.
- Document Chat **[REIMPLEMENT]**
- Document Podcasts



## Contribute 

Contributions are very welcome! A contribution can be as small as a ⭐ or even finding and creating issues.
Fine-tuning the Backend is always desired.

## Star History

<a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
 </picture>
</a>

