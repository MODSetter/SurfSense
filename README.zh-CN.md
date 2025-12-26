
![new_header](https://github.com/user-attachments/assets/e236b764-0ddc-42ff-a1f1-8fbb3d2e0e65)


<div align="center">
<a href="https://discord.gg/ejRNvftDp9">
<img src="https://img.shields.io/discord/1359368468260192417" alt="Discord">
</a>
</div>

<div align="center">

[English](README.md) | [简体中文](README.zh-CN.md)

</div>

# SurfSense

虽然像 NotebookLM 和 Perplexity 这样的工具在对任何主题/查询进行研究时令人印象深刻且非常有效，但 SurfSense 通过与您的个人知识库集成，将这一能力提升到了新的高度。它是一个高度可定制的 AI 研究助手，可以连接外部数据源，如搜索引擎（SearxNG、Tavily、LinkUp）、Slack、Linear、Jira、ClickUp、Confluence、BookStack、Gmail、Notion、YouTube、GitHub、Discord、Airtable、Google Calendar、Luma、Elasticsearch 等，未来还会支持更多。

<div align="center">
<a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter%2FSurfSense | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>


# 视频演示

https://github.com/user-attachments/assets/42a29ea1-d4d8-4213-9c69-972b5b806d58


## 播客示例

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7




## 核心功能

### 💡 **理念**: 
- 拥有您自己的高度可定制的私有 NotebookLM 和 Perplexity，并与外部数据源集成。

### 📁 **支持多种文件格式上传**
- 将您个人文件中的内容（文档、图像、视频，支持 **50+ 种文件扩展名**）保存到您自己的个人知识库。

### 🔍 **强大的搜索功能**
- 快速研究或查找已保存内容中的任何信息。

### 💬 **与已保存内容对话**
- 使用自然语言交互并获得引用答案。

### 📄 **引用答案**
- 像 Perplexity 一样获得带引用的答案。

### 🔔 **隐私保护与本地 LLM 支持**
- 完美支持 Ollama 本地大语言模型。

### 🏠 **可自托管**
- 开源且易于本地部署。

### 👥 **团队协作与 RBAC**
- 搜索空间的基于角色的访问控制
- 使用可自定义的角色（所有者、管理员、编辑者、查看者）邀请团队成员
- 对文档、聊天、连接器和设置的细粒度权限控制
- 在组织内安全共享知识库

### 🎙️ **播客功能**
- 超快速播客生成代理（在 20 秒内创建 3 分钟播客）
- 将聊天对话转换为引人入胜的音频内容
- 支持本地 TTS 提供商（Kokoro TTS）
- 支持多个 TTS 提供商（OpenAI、Azure、Google Vertex AI）

### 🤖 **深度代理架构**

#### 内置代理工具
| 工具 | 描述 |
|------|------|
| **search_knowledge_base** | 使用语义+全文混合搜索、日期过滤和连接器特定查询搜索您的个人知识库 |
| **generate_podcast** | 从聊天对话或知识库内容生成音频播客 |
| **link_preview** | 获取 URL 的 Open Graph 元数据以显示预览卡片 |
| **display_image** | 在聊天中显示带有元数据和来源归属的图像 |
| **scrape_webpage** | 从网页中提取完整内容用于分析和总结（支持 Firecrawl 或本地 Chromium/Trafilatura） |

#### 可扩展工具注册表
贡献者可以通过注册表模式轻松添加新工具：
1. 在 `surfsense_backend/app/agents/new_chat/tools/` 中创建工具工厂函数
2. 在 `registry.py` 的 `BUILTIN_TOOLS` 列表中注册

#### 可配置的系统提示词
- 通过 LLM 配置自定义系统指令
- 按配置切换引用开关
- 通过 LiteLLM 集成支持 100+ 种 LLM

### 📊 **先进的 RAG 技术**
- 支持 100+ 种大语言模型
- 支持 6000+ 种嵌入模型
- 支持所有主流重排序器（Pinecode、Cohere、Flashrank 等）
- 使用层次化索引（2 层 RAG 设置）
- 利用混合搜索（语义搜索 + 全文搜索，结合倒数排名融合）

### ℹ️ **外部数据源**
- 搜索引擎（Tavily、LinkUp）
- SearxNG（自托管实例）
- Slack
- Linear
- Jira
- ClickUp
- Confluence
- BookStack
- Notion
- Gmail
- YouTube 视频
- GitHub
- Discord
- Airtable
- Google Calendar
- Luma
- Elasticsearch
- 更多即将推出......

## 📄 **支持的文件扩展名**

| ETL 服务 | 格式 | 说明 |
|----------|------|------|
| **LlamaCloud** | 50+ 种格式 | 文档、演示文稿、电子表格、图像 |
| **Unstructured** | 34+ 种格式 | 核心格式 + 电子邮件支持 |
| **Docling** | 核心格式 | 本地处理，无需 API 密钥 |

**音频/视频**（通过 STT 服务）：`.mp3`、`.wav`、`.mp4`、`.webm` 等

### 🔖 **跨浏览器扩展**
- SurfSense 扩展可用于保存您喜欢的任何网页
- 主要用途是保存需要身份验证的受保护网页



## 功能请求与未来规划

**SurfSense 正在积极开发中。** 虽然它还未达到生产就绪状态，但您可以帮助我们加快进度。

加入 [SurfSense Discord](https://discord.gg/ejRNvftDp9) 一起塑造 SurfSense 的未来！

## 🚀 路线图

随时了解我们的开发进度和即将推出的功能！  
查看我们的公开路线图并贡献您的想法或反馈：

**📋 路线图讨论：** [SurfSense 2025-2026 路线图：深度代理、实时协作与 MCP 服务器](https://github.com/MODSetter/SurfSense/discussions/565)

**📊 看板：** [SurfSense 项目看板](https://github.com/users/MODSetter/projects/3)


## 如何开始？

### 使用 Docker 快速开始 🐳

> [!TIP]
> 对于生产部署，请使用完整的 [Docker Compose 设置](https://www.surfsense.com/docs/docker-installation)，它提供更多控制和可扩展性。

**Linux/macOS:**

```bash
docker run -d -p 3000:3000 -p 8000:8000 \
  -v surfsense-data:/data \
  --name surfsense \
  --restart unless-stopped \
  ghcr.io/modsetter/surfsense:latest
```

**Windows (PowerShell):**

```powershell
docker run -d -p 3000:3000 -p 8000:8000 `
  -v surfsense-data:/data `
  --name surfsense `
  --restart unless-stopped `
  ghcr.io/modsetter/surfsense:latest
```

**使用自定义配置（例如 OpenAI 嵌入）：**

```bash
docker run -d -p 3000:3000 -p 8000:8000 \
  -v surfsense-data:/data \
  -e EMBEDDING_MODEL=openai://text-embedding-ada-002 \
  -e OPENAI_API_KEY=your_openai_api_key \
  --name surfsense \
  --restart unless-stopped \
  ghcr.io/modsetter/surfsense:latest
```

启动后，访问 SurfSense：
- **前端**: [http://localhost:3000](http://localhost:3000)
- **后端 API**: [http://localhost:8000](http://localhost:8000)
- **API 文档**: [http://localhost:8000/docs](http://localhost:8000/docs)

**常用命令：**

```bash
docker logs -f surfsense      # 查看日志
docker stop surfsense         # 停止
docker start surfsense        # 启动
docker rm surfsense           # 删除（数据保留在卷中）
```

### 安装选项

SurfSense 提供多种入门方式：

1. **[SurfSense Cloud](https://www.surfsense.com/login)** - 无需任何设置即可试用 SurfSense 的最简单方法。
   - 无需安装
   - 即时访问所有功能
   - 非常适合快速上手

2. **快速启动 Docker（上述方法）** - 一条命令即可在本地运行 SurfSense。
   - 一体化镜像，捆绑 PostgreSQL、Redis 和所有服务
   - 非常适合评估、开发和小型部署
   - 数据通过 Docker 卷持久化

3. **[Docker Compose（生产环境）](https://www.surfsense.com/docs/docker-installation)** - 使用独立服务进行完整堆栈部署。
   - 包含 pgAdmin，通过 Web UI 进行数据库管理
   - 支持通过 `.env` 文件自定义环境变量
   - 灵活的部署选项（完整堆栈或仅核心服务）
   - 更适合生产环境，支持独立扩展服务

4. **[手动安装](https://www.surfsense.com/docs/manual-installation)** - 适合希望对设置有更多控制或需要自定义部署的用户。

Docker 和手动安装指南都包含适用于 Windows、macOS 和 Linux 的详细操作系统特定说明。

在自托管安装之前，请确保完成[先决条件设置步骤](https://www.surfsense.com/docs/)，包括：
- 身份验证设置（可选 - 默认为 LOCAL 身份验证）
- **文件处理 ETL 服务**（可选 - 默认为 Docling）：
  - Docling（默认，本地处理，无需 API 密钥，支持 PDF、Office 文档、图像、HTML、CSV）
  - Unstructured.io API 密钥（支持 34+ 种格式）
  - LlamaIndex API 密钥（增强解析，支持 50+ 种格式）
- 其他根据用例需要的 API 密钥



## 技术栈


 ### **后端** 

-  **FastAPI**：现代、快速的 Python Web 框架，用于构建 API
  
-  **PostgreSQL with pgvector**：具有向量搜索功能的数据库，用于相似性搜索

-  **SQLAlchemy**：SQL 工具包和 ORM（对象关系映射），用于数据库交互

-  **Alembic**：SQLAlchemy 的数据库迁移工具

-  **FastAPI Users**：使用 JWT 和 OAuth 支持的身份验证和用户管理

-  **深度代理**：基于 LangGraph 构建的自定义代理框架，用于推理和行动的 AI 代理，支持可配置工具

-  **LangGraph**：用于开发具有对话持久性的有状态 AI 代理的框架

-  **LangChain**：用于开发 AI 驱动应用程序的框架

-  **LiteLLM**：通用 LLM 集成，支持 100+ 种模型（OpenAI、Anthropic、Ollama 等）

-  **Rerankers**：先进的结果排序，提高搜索相关性

-  **混合搜索**：结合向量相似性和全文搜索，使用倒数排名融合 (RRF) 获得最佳结果

-  **向量嵌入**：文档和文本嵌入，用于语义搜索

-  **pgvector**：PostgreSQL 扩展，用于高效的向量相似性操作

-  **Redis**：内存数据结构存储，用作 Celery 的消息代理和结果后端

-  **Celery**：分布式任务队列，用于处理异步后台任务（文档处理、播客生成等）

-  **Flower**：Celery 任务队列的实时监控和管理工具

-  **Chonkie**：先进的文档分块和嵌入库
 - 使用 `AutoEmbeddings` 灵活选择嵌入模型
 -  `LateChunker` 基于嵌入模型的最大序列长度优化文档分块

  
---
 ### **前端**

-  **Next.js**：React 框架，具有应用路由器、服务器组件、自动代码拆分和优化渲染功能

-  **React**：用于构建用户界面的 JavaScript 库

-  **TypeScript**：JavaScript 的静态类型检查，提升代码质量和开发体验

- **Vercel AI SDK Kit UI Stream Protocol**：创建可扩展的聊天 UI

-  **Tailwind CSS**：实用优先的 CSS 框架，用于构建自定义 UI 设计

-  **Shadcn**：无头组件库

-  **Motion（Framer Motion）**：React 动画库


 ### **DevOps**

-  **Docker**：容器平台，用于跨环境的一致部署
  
-  **Docker Compose**：用于定义和运行多容器 Docker 应用程序的工具

-  **pgAdmin**：Docker 设置中包含的基于 Web 的 PostgreSQL 管理工具


### **扩展** 
基于 Plasmo 的 Manifest v3


## 贡献

非常欢迎贡献！贡献可以小到一个 ⭐，甚至是发现和创建问题。
后端的微调总是受欢迎的。

### 添加新的代理工具

想要为 SurfSense 代理添加新工具？非常简单：

1. 在 `surfsense_backend/app/agents/new_chat/tools/my_tool.py` 中创建您的工具文件
2. 在 `registry.py` 中注册：

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

有关详细的贡献指南，请参阅我们的 [CONTRIBUTING.md](CONTRIBUTING.md) 文件。

## Star 历史

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
