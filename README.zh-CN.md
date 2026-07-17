<a href="https://www.surfsense.com/"><img width="1584" height="396" alt="SurfSense，面向 AI 智能体的开源开放网络研究平台" src="https://github.com/user-attachments/assets/9361ef58-1753-4b6e-b275-5020d8847261" /></a>



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
<div align="center">
<a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter%2FSurfSense | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>

# SurfSense：面向开放网络研究的 NotebookLM

SurfSense 是**面向 AI 智能体的开源开放网络研究平台**，就像 NotebookLM，但配备了实时数据连接器。你的智能体可以通过一个 **REST API** 或 **MCP 服务器**，利用来自 **Reddit、YouTube、Instagram、TikTok、Google Maps、Google Search 以及开放网络上任意页面**的结构化数据研究实时网络。定时和事件触发的智能体会把发现的内容转化为简报和预警，内置的知识库则让每一条发现都可搜索、可引用。

> [!NOTE]
> **📢 致我们的 NotebookLM 替代品用户**
>
> 在过去几个月里，我们把 SurfSense 打造成了针对个人知识的最佳通用研究智能体，这段旅程为我们赢得了一个令我们由衷自豪的社区。如今，Claude、OpenCode、Hermes、OpenClaw 等智能体工具已经证明智能体就是未来，在静态索引上进行推理正在成为每个有能力的智能体开箱即用的功能。而智能体仍然缺少的是**来自答案真正所在之处的实时数据，以及围绕它的工作流**。这正是我们全力投入的方向：为智能体提供研究开放网络的基础原语。
>
> **你所依赖的一切功能都不会消失。**你的知识库、带引用的对话、报告、播客、演示文稿、自动化以及协作聊天都会继续可用，自托管也依然免费且开源。完整公告请阅读[我们的更新日志](https://www.surfsense.com/changelog)。

## 目录

- [为什么智能体需要 SurfSense](#为什么智能体需要-surfsense)
- [实时数据连接器](#实时数据连接器)
- [快速开始](#快速开始)
- [开箱即用的其他能力](#开箱即用的其他能力)
- [SurfSense 与同类工具的对比](#surfsense-与同类工具的对比)
- [路线图](#路线图)
- [参与贡献](#参与贡献)

## 为什么智能体需要 SurfSense

问任何一个有能力的智能体“自发布以来 Reddit 上对这款产品的评价如何？”或者“这十个地点的评论到底在抱怨什么？”，它都找不到可信赖的数据来源。官方平台 API 要么有速率限制、要么按企业级定价、要么根本不存在；自建抓取管线非常脆弱；而用 LLM 驱动浏览器，每个页面都要消耗数分钟和大量 token。SurfSense 转而为智能体提供这些基础原语：

- **一个覆盖所有数据来源的强类型接口。**每个连接器都是返回结构化 JSON 的 REST 端点——帖子、评论、字幕转录、点评、搜索结果页、网页。不用赌速率限制，不用解析 HTML，也没有浏览器循环。
- **一个 MCP 服务器**，把每个连接器都作为原生工具（`surfsense_reddit_scrape`、`surfsense_google_search` 等）暴露给 Claude、Cursor 或任何智能体框架。
- **一套智能体运行框架**，而不只是原始数据：重试、结构化输出和额度计量都已内置，智能体可以从一个问题直达一份带引用的简报，无需你自己搭建管线。
- **开源且可自托管**，你的研究数据始终留在你自己的基础设施上。

## 实时数据连接器

| 连接器 | 你的智能体能获得什么 | 了解更多 |
|---|---|---|
| **Reddit** | 帖子、评论和子版块信息流，不受官方 API 速率限制 | [Reddit Scraper API](https://www.surfsense.com/reddit) |
| **YouTube** | 大规模获取视频、字幕转录和评论串 | [YouTube Scraper API](https://www.surfsense.com/youtube) |
| **Instagram** | 公开主页、帖子和 Reels，无需 Graph API | [Instagram Scraper API](https://www.surfsense.com/instagram) |
| **TikTok** | 视频、评论、话题标签和主页，无需 Research API 审批 | [TikTok Scraper API](https://www.surfsense.com/tiktok) |
| **Google Maps** | 地点、评分和评论，用于本地商户研究 | [Google Maps Scraper API](https://www.surfsense.com/google-maps) |
| **Google Search** | 实时搜索结果页，用于搜索研究和监控 | [Google Search API](https://www.surfsense.com/google-search) |
| **Web Crawl** | 把开放网络上的任意页面转为干净、结构化的内容 | [Web Crawling API](https://www.surfsense.com/web-crawl) |
| **外部 MCP 连接器** | 将任意 MCP 服务器接入你的智能体，Notion、Slack、Jira 等支持一键 OAuth | [External MCP Connectors](https://www.surfsense.com/external-mcp-connectors) |

连接器目录正在向社交平台和搜索之外扩展；每个新数据源都会作为强类型端点落在同一套 API 和 MCP 服务器上。

计费采用按量付费：连接器按实际返回的条目计费，爬取按成功抓取的页面计费，失败的调用永不计费。自托管部署默认关闭计费。详见[定价](https://www.surfsense.com/pricing)。

## 快速开始

### 在代码中调用连接器

每个连接器都是一个 REST 端点，你可以用任何语言、凭借你的 SurfSense API 密钥来调用：

```bash
curl -X POST "$SURFSENSE_API_URL/workspaces/$WORKSPACE_ID/scrapers/reddit/scrape" \
  -H "Authorization: Bearer $SURFSENSE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "search_queries": ["your brand"],
    "community": "SaaS",
    "sort": "top",
    "time_filter": "week"
  }'
```

每个[连接器页面](https://www.surfsense.com/connectors)都提供 Python、JavaScript、Go、PHP、Ruby、Java 和 C# 的可直接复制粘贴的示例。

### 通过 MCP 把工具交给你的智能体

把 SurfSense MCP 服务器添加到 Claude、Cursor 或你自己的智能体框架：

```json
{
  "mcpServers": {
    "surfsense": {
      "url": "https://mcp.surfsense.com/mcp",
      "headers": { "Authorization": "Bearer ${SURFSENSE_API_KEY}" }
    }
  }
}
```

现在，你的智能体就可以把每个连接器当作原生工具来调用。完整工具列表请查看 [SurfSense MCP 服务器](https://www.surfsense.com/mcp-server) 页面，也可以通过 [`surfsense_mcp`](./surfsense_mcp) 在本地运行该服务器。

### 使用云端服务

访问 [surfsense.com](https://www.surfsense.com)，登录后用自然语言向智能体索取实时网络数据。新账户自带 5 美元免费额度，无需订阅。

### 免费自托管

在你自己的基础设施上运行整个平台，包括连接器、智能体、自动化和 MCP 服务器。自托管部署默认关闭计费，抓取、爬取和智能体运行只受你的硬件和你自带的模型密钥限制。

**前置条件：**必须已安装并运行 [Docker Desktop](https://www.docker.com/products/docker-desktop/)。

Linux/macOS：

```bash
curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
```

Windows：

```bash
irm https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.ps1 | iex
```

安装脚本会自动配置 [Watchtower](https://github.com/nicholas-fedor/watchtower) 以实现每日自动更新。如需跳过，请加上 `--no-watchtower` 参数。关于 Docker Compose、手动安装及其他部署方式，请参阅[文档](https://www.surfsense.com/docs/)。

## 开箱即用的其他能力

让 SurfSense 成为领先的开源 NotebookLM 替代品的那套研究工作区依然都在，而且你的智能体收集到的一切都会汇入其中。

**知识库**

- 上传 PDF、Office 文档、图片和音频，或同步 **Google Drive、OneDrive 和 Dropbox**。支持 50 多种文件格式。
- 混合语义与全文搜索，提供 Perplexity 风格的带引用回答。
- AI 文件整理功能按来源、日期和主题自动归类文档。

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="与你的 PDF 和文档对话" /></p>

**成果工作室**

- AI 报告生成器，可导出为 PDF、DOCX、HTML、LaTeX、EPUB、ODT 或纯文本。
- 20 秒内基于任意文档或文件夹生成双主持人 AI 播客。
- 可编辑的幻灯片、带旁白的视频概览以及 AI 图像生成。

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ReportGenGif_compressed.gif" alt="AI 报告生成器" /></p>

**自动化**

- 按计划或响应事件运行完整的智能体回合，用自然语言描述即可，结果自动写回 Notion、Slack、Linear 和 Jira。

**团队协作**

- 支持评论和提及的实时协作 AI 聊天。
- 基于角色的访问控制（RBAC），提供所有者、管理员、编辑者和查看者角色。

<p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeChatGif.gif" alt="协作 AI 聊天" /></p>

**桌面应用**

在电脑上的每个应用中获得原生 AI 辅助。从[最新版本](https://github.com/MODSetter/SurfSense/releases/latest)下载。

- **General Assist**：通过全局快捷键在任意应用中唤起 SurfSense。
- **Quick Assist**：在任意位置选中文本，让 AI 解释、改写或据此执行操作。
- **Screenshot Assist**：截取屏幕上任意区域，向 AI 提问。
- **Watch Local Folder**：把本地文件夹自动同步到知识库。将它指向你的 Obsidian 仓库，让笔记随时可搜索。

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/quick_assist.gif" alt="Quick Assist" /></p>

**无供应商锁定**

- 通过 OpenAI 规范和 LiteLLM 支持 100 多种 LLM，包括 GPT-5.5、Claude Sonnet 5 和 Gemini 3.1 Pro。
- 支持 6,000 多种嵌入模型和所有主流重排序器。
- 完整支持本地和私有 LLM（vLLM、Ollama），你的数据始终属于你。

## 视频智能体示例

https://github.com/user-attachments/assets/012a7ffa-6f76-4f06-9dda-7632b470057a

## 播客智能体示例

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7

## 如何进行实时协作（Beta）

1. 进入成员管理页面并创建邀请。

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="邀请成员" /></p>

2. 队友加入后，该工作区即变为共享。

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="邀请加入流程" /></p>

3. 将聊天设为共享，即可与团队实时协作，并通过评论标记队友。

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeCommentsFlow.gif" alt="实时评论" /></p>

## SurfSense 与同类工具的对比

SurfSense 是唯一一款把面向人的 NotebookLM 式研究工作区与面向智能体的实时数据原语结合在一起的开源产品。下面是它与每一类工具的对比。

**对比浏览器智能体（Browserbase、Browser Use）。**浏览器智能体让 LLM 在循环中驱动一个真实浏览器——当任务需要点击、登录或填写表单时，这是正确的工具。但大多数研究都是只读的检索，而对于检索来说，“LLM 驱动浏览器”的循环每个页面都要花费数分钟和数千 token。一次 SurfSense 连接器调用只是一个 HTTP 请求：几秒完成、结果确定，而且不用花一个 token 去决定该点哪里。

**对比抓取 API（Firecrawl）。**抓取 API 很擅长把通用网页转成 markdown，但一团 markdown 仍然需要你的智能体从行文中解析结构，而且它们在 Reddit、TikTok、Instagram 这类有反爬保护的平台上会明显退化。SurfSense 连接器返回平台原生的结构化条目——帖子、评论、字幕转录、点评——并且只按实际返回的条目计费；失败的调用永不计费。

**对比搜索 API（Exa、Tavily、Parallel）。**搜索 API 基于网络索引作答，对于“帮我找关于 X 的页面”来说是正确的工具。但它们拉不到 Reddit 帖子串的评论、TikTok 的用户反应、YouTube 的字幕转录或 Google Maps 的点评——而答案往往就藏在这些地方。

**对比爬虫市场（Apify）。**市场提供成千上万个社区 actor，每个都有自己的 schema、质量和定价。SurfSense 是一个强类型 API 加一个 MCP 服务器，背后还有智能体运行框架和研究工作区，而且它是开源的。

### SurfSense 对比 Google NotebookLM

还在把我们当作 NotebookLM 替代品来比较？这里是坦诚的对比。

| 功能 | Google NotebookLM | SurfSense |
|---------|-------------------|-----------|
| **面向智能体的实时网络数据** | 无 | 通过 REST API 和 MCP 提供 Reddit、YouTube、Instagram、TikTok、Google Maps、Google Search 和网页爬取连接器 |
| **MCP 服务器** | 无 | 每个连接器都作为原生智能体工具暴露，还可自带 MCP 服务器并使用一键 OAuth 应用 |
| **每个笔记本的来源数** | 50 个（免费版）至 600 个（Ultra 版，249.99 美元/月） | 无限制 |
| **笔记本数量** | 100 个（免费版）至 500 个（付费档位） | 无限制 |
| **来源大小限制** | 每个来源 50 万字 / 200MB | 无限制 |
| **定价** | 免费档；Pro 19.99 美元/月，Ultra 249.99 美元/月 | 自托管免费且开源；云端按量付费，附赠 5 美元免费额度 |
| **LLM 支持** | 仅 Google Gemini | 通过 OpenAI 规范和 LiteLLM 支持 100 多种 LLM |
| **嵌入模型** | 仅 Google | 6,000 多种嵌入模型，所有主流重排序器 |
| **本地 / 私有 LLM** | 不支持 | 完整支持（vLLM、Ollama），你的数据始终属于你 |
| **可自托管** | 否 | 是，Docker 一行命令或完整 Docker Compose |
| **开源** | 否 | 是 |
| **知识库来源** | Google Drive、YouTube、网站 | 文件上传、Google Drive、OneDrive、Dropbox、本地文件夹同步以及爬取的网页 |
| **文件格式支持** | PDF、Docs、Slides、Sheets、CSV、Word、EPUB、图片、网页 URL、YouTube | 50 多种格式：文档、图片、视频，通过 LlamaCloud、Unstructured 或 Docling（本地）解析 |
| **搜索** | 语义搜索 | 混合语义 + 全文搜索，带分层索引和倒数排名融合 |
| **带引用的回答** | 有 | 有，Perplexity 风格的引用回答 |
| **智能体架构** | 无 | 有，由 [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) 驱动，具备规划、子智能体和文件系统访问能力 |
| **AI 自动化与智能体** | 无 | 定时工作流、事件触发以及通过聊天构建的无代码自动化，可写回 Notion、Slack、Linear 和 Jira |
| **实时多人协作** | 共享笔记本，仅有查看者/编辑者角色（无实时聊天） | RBAC 提供所有者 / 管理员 / 编辑者 / 查看者角色，支持实时聊天和评论串 |
| **视频生成** | 通过 Veo 3 生成电影级视频概览（仅 Ultra 版） | 已提供（此项 NotebookLM 更强，我们正在积极改进） |
| **演示文稿生成** | 幻灯片更美观但不可编辑 | 可编辑的幻灯片式演示文稿 |
| **播客生成** | 音频概览，支持自定义主持人和语言 | 已提供，支持多种 TTS 服务商（此项 NotebookLM 更强，我们正在积极改进） |
| **桌面应用** | 无 | 原生应用，包含 General Assist、Quick Assist、Screenshot Assist 和本地文件夹同步 |

## 功能请求与未来规划

**SurfSense 正在积极开发中。**虽然它尚未达到生产就绪状态，但你可以帮助我们加快进度。

加入 [SurfSense Discord](https://discord.gg/ejRNvftDp9)，一起塑造 SurfSense 的未来！

## 路线图

随时了解我们的开发进度和即将推出的功能。查看我们的公开路线图，贡献你的想法或反馈：

**路线图讨论：**[SurfSense 2026 Roadmap](https://github.com/MODSetter/SurfSense/discussions/565)

**看板：**[SurfSense Project Board](https://github.com/users/MODSetter/projects/3)

## 参与贡献

欢迎一切形式的贡献，从点星标、报告缺陷到后端改进。请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 开始参与。

感谢所有 Surfer：

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" />
</a>

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
