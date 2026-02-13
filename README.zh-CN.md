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

[English](README.md) | [Español](README.es.md) | [Português](README.pt-BR.md) | [हिन्दी](README.hi.md) | [简体中文](README.zh-CN.md)

</div>

# SurfSense
将任何 LLM 连接到您的内部知识源，并与团队成员实时聊天。NotebookLM、Perplexity 和 Glean 的开源替代方案。

SurfSense 是一个高度可定制的 AI 研究助手，可以连接外部数据源，如搜索引擎（SearxNG、Tavily、LinkUp）、Google Drive、Slack、Microsoft Teams、Linear、Jira、ClickUp、Confluence、BookStack、Gmail、Notion、YouTube、GitHub、Discord、Airtable、Google Calendar、Luma、Circleback、Elasticsearch、Obsidian 等，未来还会支持更多。

<div align="center">
<a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter%2FSurfSense | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>


# 视频演示

https://github.com/user-attachments/assets/cc0c84d3-1f2f-4f7a-b519-2ecce22310b1


## 播客示例

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7




## 核心功能

### 💡 **理念**: 
- NotebookLM、Perplexity 和 Glean 的开源替代方案。将任何 LLM 连接到您的内部知识源，并与团队实时协作。
### 📁 **支持多种文件格式上传**
- 将您个人文件中的内容（文档、图像、视频，支持 **50+ 种文件扩展名**）保存到您自己的个人知识库。
### 🔍 **强大的搜索功能**
- 快速研究或查找已保存内容中的任何信息。
### 💬 **与已保存内容对话**
- 使用自然语言交互并获得引用答案。
### 📄 **引用答案**
- 像 Perplexity 一样获得带引用的答案。
### 🧩 **通用兼容性**
- 通过 OpenAI 规范和 LiteLLM 连接几乎任何推理提供商。
### 🔔 **隐私保护与本地 LLM 支持**
- 完美支持 vLLM 和 Ollama 等本地大语言模型。
### 🏠 **可自托管**
- 开源且易于本地部署。
### 👥 **团队协作与 RBAC**
- 搜索空间的基于角色的访问控制
- 使用可自定义的角色（所有者、管理员、编辑者、查看者）邀请团队成员
- 对文档、聊天、连接器和设置的细粒度权限控制
- 在组织内安全共享知识库
- 团队聊天实时更新，支持评论线程中的"关于聊天的讨论"
### 🎙️ 播客功能
- 超快速播客生成代理（在 20 秒内创建 3 分钟播客）
- 将聊天对话转换为引人入胜的音频内容
- 支持本地 TTS 提供商（Kokoro TTS）
- 支持多个 TTS 提供商（OpenAI、Azure、Google Vertex AI）

### 🤖 **深度代理架构**
- 基于 [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) 构建 - 支持规划、子代理和文件系统的复杂任务处理代理。

### 📊 **先进的 RAG 技术**
- 支持 100+ 种大语言模型
- 支持 6000+ 种嵌入模型
- 支持所有主流重排序器（Pinecone、Cohere、Flashrank 等）
- 使用层次化索引（2 层 RAG 设置）
- 利用混合搜索（语义搜索 + 全文搜索，结合倒数排名融合）

### ℹ️ **外部数据源**
- 搜索引擎（Tavily、LinkUp）
- SearxNG（自托管实例）
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
- YouTube 视频
- GitHub
- Discord
- Airtable
- Google Calendar
- Luma
- Circleback
- Elasticsearch
- Obsidian
- 更多即将推出......

## 📄 **支持的文件扩展名**

| ETL 服务 | 格式 | 说明 |
|----------|------|------|
| **LlamaCloud** | 50+ 种格式 | 文档、演示文稿、电子表格、图像 |
| **Unstructured** | 34+ 种格式 | 核心格式 + 电子邮件支持 |
| **Docling** | 核心格式 | 本地处理，无需 API 密钥 |

**音频/视频**（通过 STT 服务）：`.mp3`、`.wav`、`.mp4`、`.webm` 等

### 🔖 跨浏览器扩展
- SurfSense 扩展可用于保存您喜欢的任何网页。
- 主要用途是保存需要身份验证的受保护网页。



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

**使用自定义配置：**

您可以使用 `-e` 标志传递任何环境变量：

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
> - 如果部署在带有 HTTPS 的反向代理后面，请添加 `-e BACKEND_URL=https://api.yourdomain.com`

启动后，访问 SurfSense：
- **前端**: [http://localhost:3000](http://localhost:3000)
- **后端 API**: [http://localhost:8000](http://localhost:8000)
- **API 文档**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Electric-SQL**: [http://localhost:5133](http://localhost:5133)

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
