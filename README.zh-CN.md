
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

虽然像 NotebookLM 和 Perplexity 这样的工具在对任何主题/查询进行研究时令人印象深刻且非常有效，但 SurfSense 通过与您的个人知识库集成，将这一能力提升到了新的高度。它是一个高度可定制的 AI 研究助手，可以连接外部数据源，如搜索引擎（SearxNG、Tavily、LinkUp）、Slack、Linear、Jira、ClickUp、Confluence、Gmail、Notion、YouTube、GitHub、Discord、Airtable、Google Calendar、Luma、Elasticsearch 等，未来还会支持更多。

<div align="center">
<a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter%2FSurfSense | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>


# 视频演示


https://github.com/user-attachments/assets/d9221908-e0de-4b2f-ac3a-691cf4b202da


## 播客示例

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7




## 核心功能

### 💡 **理念**: 
拥有您自己的高度可定制的私有 NotebookLM 和 Perplexity，并与外部数据源集成。

### 📁 **支持多种文件格式上传**
将您个人文件中的内容（文档、图像、视频，支持 **50+ 种文件扩展名**）保存到您自己的个人知识库。

### 🔍 **强大的搜索功能**
快速研究或查找已保存内容中的任何信息。

### 💬 **与已保存内容对话**
使用自然语言交互并获得引用答案。

### 📄 **引用答案**
像 Perplexity 一样获得带引用的答案。

### 🔔 **隐私保护与本地 LLM 支持**
完美支持 Ollama 本地大语言模型。

### 🏠 **可自托管**
开源且易于本地部署。

### 🎙️ **播客功能**
- 超快速播客生成代理（在 20 秒内创建 3 分钟播客）
- 将聊天对话转换为引人入胜的音频内容
- 支持本地 TTS 提供商（Kokoro TTS）
- 支持多个 TTS 提供商（OpenAI、Azure、Google Vertex AI）

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

> **注意**：文件格式支持取决于您的 ETL 服务配置。LlamaCloud 支持 50+ 种格式，Unstructured 支持 34+ 种核心格式，Docling 支持核心格式（本地处理、注重隐私、无需 API 密钥）。

### 文档与文本
**LlamaCloud**: `.pdf`, `.doc`, `.docx`, `.docm`, `.dot`, `.dotm`, `.rtf`, `.txt`, `.xml`, `.epub`, `.odt`, `.wpd`, `.pages`, `.key`, `.numbers`, `.602`, `.abw`, `.cgm`, `.cwk`, `.hwp`, `.lwp`, `.mw`, `.mcw`, `.pbd`, `.sda`, `.sdd`, `.sdp`, `.sdw`, `.sgl`, `.sti`, `.sxi`, `.sxw`, `.stw`, `.sxg`, `.uof`, `.uop`, `.uot`, `.vor`, `.wps`, `.zabw`

**Unstructured**: `.doc`, `.docx`, `.odt`, `.rtf`, `.pdf`, `.xml`, `.txt`, `.md`, `.markdown`, `.rst`, `.html`, `.org`, `.epub`

**Docling**: `.pdf`, `.docx`, `.html`, `.htm`, `.xhtml`, `.adoc`, `.asciidoc`

### 演示文稿
**LlamaCloud**: `.ppt`, `.pptx`, `.pptm`, `.pot`, `.potm`, `.potx`, `.odp`, `.key`

**Unstructured**: `.ppt`, `.pptx`

**Docling**: `.pptx`

### 电子表格与数据
**LlamaCloud**: `.xlsx`, `.xls`, `.xlsm`, `.xlsb`, `.xlw`, `.csv`, `.tsv`, `.ods`, `.fods`, `.numbers`, `.dbf`, `.123`, `.dif`, `.sylk`, `.slk`, `.prn`, `.et`, `.uos1`, `.uos2`, `.wk1`, `.wk2`, `.wk3`, `.wk4`, `.wks`, `.wq1`, `.wq2`, `.wb1`, `.wb2`, `.wb3`, `.qpw`, `.xlr`, `.eth`

**Unstructured**: `.xls`, `.xlsx`, `.csv`, `.tsv`

**Docling**: `.xlsx`, `.csv`

### 图像
**LlamaCloud**: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.svg`, `.tiff`, `.webp`, `.html`, `.htm`, `.web`

**Unstructured**: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.heic`

**Docling**: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.tif`, `.webp`

### 音频与视频 **（始终支持）**
`.mp3`, `.mpga`, `.m4a`, `.wav`, `.mp4`, `.mpeg`, `.webm`

### 电子邮件与通讯
**Unstructured**: `.eml`, `.msg`, `.p7s`

### 🔖 **跨浏览器扩展**
- SurfSense 扩展可用于保存您喜欢的任何网页
- 主要用途是保存需要身份验证的受保护网页



## 功能请求与未来规划

**SurfSense 正在积极开发中。** 虽然它还未达到生产就绪状态，但您可以帮助我们加快进度。

加入 [SurfSense Discord](https://discord.gg/ejRNvftDp9) 一起塑造 SurfSense 的未来！

## 🚀 路线图

随时了解我们的开发进度和即将推出的功能！  
查看我们的公开路线图并贡献您的想法或反馈：

**查看路线图：** [SurfSense 路线图 (GitHub Projects)](https://github.com/users/MODSetter/projects/2)


## 如何开始？

### 安装选项

SurfSense 提供三种入门方式：

1. **[SurfSense Cloud](https://www.surfsense.com/login)** - 无需任何设置即可试用 SurfSense 的最简单方法。
   - 无需安装
   - 即时访问所有功能
   - 非常适合快速上手

2. **[Docker 安装（推荐用于自托管）](https://www.surfsense.net/docs/docker-installation)** - 通过容器化所有依赖项，轻松启动和运行 SurfSense。
   - 包含 pgAdmin，通过 Web UI 进行数据库管理
   - 支持通过 `.env` 文件自定义环境变量
   - 灵活的部署选项（完整堆栈或仅核心服务）
   - 无需在环境之间手动编辑配置文件

3. **[手动安装](https://www.surfsense.net/docs/manual-installation)** - 适合希望对设置有更多控制或需要自定义部署的用户。

Docker 和手动安装指南都包含适用于 Windows、macOS 和 Linux 的详细操作系统特定说明。

在自托管安装之前，请确保完成[先决条件设置步骤](https://www.surfsense.net/docs/)，包括：
- 身份验证设置
- **文件处理 ETL 服务**（选择其一）：
  - Unstructured.io API 密钥（支持 34+ 种格式）
  - LlamaIndex API 密钥（增强解析，支持 50+ 种格式）
  - Docling（本地处理，无需 API 密钥，支持 PDF、Office 文档、图像、HTML、CSV）
- 其他所需的 API 密钥

## 截图

**研究助手** 

![updated_researcher](https://github.com/user-attachments/assets/e22c5d86-f511-4c72-8c50-feba0c1561b4)

**搜索空间** 

![search_spaces](https://github.com/user-attachments/assets/e254c38c-f937-44b6-9e9d-770db583d099)

**管理文档** 
![documents](https://github.com/user-attachments/assets/7001e306-eb06-4009-89c6-8fadfdc3fc4d)

**播客助手** 
![podcasts](https://github.com/user-attachments/assets/6cb82ffd-9e14-4172-bc79-67faf34c4c1c)


**对话助手** 

![git_chat](https://github.com/user-attachments/assets/bb352d52-1c6d-4020-926b-722d0b98b491)

**浏览器扩展**

![ext1](https://github.com/user-attachments/assets/1f042b7a-6349-422b-94fb-d40d0df16c40)

![ext2](https://github.com/user-attachments/assets/a9b9f1aa-2677-404d-b0a0-c1b2dddf24a7)


## 技术栈


 ### **后端** 

-  **FastAPI**：现代、快速的 Python Web 框架，用于构建 API
  
-  **PostgreSQL with pgvector**：具有向量搜索功能的数据库，用于相似性搜索

-  **SQLAlchemy**：SQL 工具包和 ORM（对象关系映射），用于数据库交互

-  **Alembic**：SQLAlchemy 的数据库迁移工具

-  **FastAPI Users**：使用 JWT 和 OAuth 支持的身份验证和用户管理

-  **LangGraph**：用于开发 AI 代理的框架
  
-  **LangChain**：用于开发 AI 驱动应用程序的框架

-  **LLM 集成**：通过 LiteLLM 与大语言模型集成

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

-  **Next.js 15.2.3**：React 框架，具有应用路由器、服务器组件、自动代码拆分和优化渲染功能

-  **React 19.0.0**：用于构建用户界面的 JavaScript 库

-  **TypeScript**：JavaScript 的静态类型检查，提升代码质量和开发体验

- **Vercel AI SDK Kit UI Stream Protocol**：创建可扩展的聊天 UI

-  **Tailwind CSS 4.x**：实用优先的 CSS 框架，用于构建自定义 UI 设计

-  **Shadcn**：无头组件库

-  **Lucide React**：作为 React 组件实现的图标集

-  **Framer Motion**：React 动画库

-  **Sonner**：Toast 通知库

-  **Geist**：Vercel 的字体系列

-  **React Hook Form**：表单状态管理和验证

-  **Zod**：TypeScript 优先的模式验证，带静态类型推断

-  **@hookform/resolvers**：用于在 React Hook Form 中使用验证库的解析器

-  **@tanstack/react-table**：用于构建强大表格和数据网格的无头 UI


 ### **DevOps**

-  **Docker**：容器平台，用于跨环境的一致部署
  
-  **Docker Compose**：用于定义和运行多容器 Docker 应用程序的工具

-  **pgAdmin**：Docker 设置中包含的基于 Web 的 PostgreSQL 管理工具


### **扩展** 
基于 Plasmo 的 Manifest v3


## 贡献

非常欢迎贡献！贡献可以小到一个 ⭐，甚至是发现和创建问题。
后端的微调总是受欢迎的。

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
