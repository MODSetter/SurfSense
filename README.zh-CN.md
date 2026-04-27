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
<div align="center">
<a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter%2FSurfSense | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>

# SurfSense

NotebookLM 是目前最好、最实用的 AI 平台之一，但当你开始经常使用它时，你也会感受到它的局限性，总觉得还有不足之处。

1. 一个笔记本中可以添加的来源数量有限制。
2. 可以拥有的笔记本数量有限制。
3. 来源不能超过 500,000 个单词和 200MB。
4. 你被锁定在 Google 服务中（LLM、使用模型等），没有配置选项。
5. 有限的外部数据源和服务集成。
6. NotebookLM 代理专门针对学习和研究进行了优化，但你可以用源数据做更多事情。
7. 缺乏多人协作支持。

...还有更多。

**SurfSense 正是为了解决这些问题而生。** SurfSense 赋予你：

- **控制你的数据流** - 保持数据私密和安全。
- **无数据限制** - 添加无限数量的来源和笔记本。
- **无供应商锁定** - 配置任何 LLM、图像、TTS 和 STT 模型。
- **25+ 外部数据源** - 从 Google Drive、OneDrive、Dropbox、Notion 和许多其他外部服务添加你的来源。
- **实时多人协作支持** - 在共享笔记本中轻松与团队成员协作。
- **桌面应用** - 通过 Quick Assist、General Assist、Screenshot Assist 和本地文件夹同步在任何应用程序中获得 AI 助手。

...更多功能即将推出。



## 视频代理示例

https://github.com/user-attachments/assets/012a7ffa-6f76-4f06-9dda-7632b470057a



## 播客代理示例

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7


## 如何使用 SurfSense

### Cloud

1. 访问 [surfsense.com](https://www.surfsense.com) 并登录。

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/LoginFlowGif.gif" alt="登录" /></p>

2. 连接您的连接器并同步。启用定期同步以保持连接器数据更新。

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ConnectorFlowGif.gif" alt="连接器" /></p>

3. 在连接器数据索引期间，上传文档。

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/DocUploadGif.gif" alt="上传文档" /></p>

4. 一切索引完成后，尽管提问（使用场景）：

   - 桌面应用 — General Assist

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/general_assist.gif" alt="General Assist" /></p>

   - 桌面应用 — Quick Assist

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/quick_assist.gif" alt="Quick Assist" /></p>

   - 桌面应用 — Screenshot Assist

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/screenshot_assist.gif" alt="Screenshot Assist" /></p>

   - 桌面应用 — Watch Local Folder

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/folder_watch.gif" alt="Watch Local Folder" /></p>

   - 视频生成

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/video_gen_gif.gif" alt="视频生成" /></p>

   - 基本搜索和引用

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BSNCGif.gif" alt="搜索和引用" /></p>

   - 文档提及问答

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="文档提及问答" /></p>
   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="文档提及问答" /></p>

   - 报告生成和导出（PDF、DOCX、HTML、LaTeX、EPUB、ODT、纯文本）

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ReportGenGif_compressed.gif" alt="报告生成" /></p>

   - 播客生成

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/PodcastGenGif.gif" alt="播客生成" /></p>

   - 图像生成

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ImageGenGif.gif" alt="图像生成" /></p>

   - 更多功能即将推出。


### 自托管

在您自己的基础设施上运行 SurfSense，实现完全的数据控制和隐私保护。

**前置条件：** 需要安装并运行 [Docker Desktop](https://www.docker.com/products/docker-desktop/)。

#### Linux/MacOS 用户：

```bash
curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
```

#### Windows 用户：

```powershell
irm https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.ps1 | iex
```

安装脚本会自动配置 [Watchtower](https://github.com/nicholas-fedor/watchtower) 以实现每日自动更新。如需跳过，请添加 `--no-watchtower` 参数。

如需 Docker Compose、手动安装及其他部署方式，请查看[文档](https://www.surfsense.com/docs/)。

### 桌面应用

SurfSense 还提供桌面应用，将 AI 助手带到您计算机上的每个应用程序中。从[最新版本](https://github.com/MODSetter/SurfSense/releases/latest)下载。

桌面应用包含以下强大功能：

- **General Assist** — 通过全局快捷键从任何应用程序即时启动 SurfSense。
- **Quick Assist** — 在任何位置选中文本，然后让 AI 解释、改写或对其执行操作。
- **Screenshot Assist** — 在屏幕上框选区域并附加到聊天，让回复基于您的知识库。
- **Watch Local Folder** — 监视本地文件夹，自动将文件更改同步到您的知识库。**Pro tip：** 将其指向您的 Obsidian vault，让笔记在 SurfSense 中随时可搜索。

所有功能均基于您选择的搜索空间运行，确保回答始终以您自己的数据为依据。

### 如何实时协作（Beta）

1. 前往成员管理页面并创建邀请。

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="邀请成员" /></p>

2. 队友加入后，该 SearchSpace 变为共享。

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="邀请加入流程" /></p>

3. 将聊天设为共享。

   <p align="center"><img src="https://github.com/user-attachments/assets/17b93904-0888-4c3a-ac12-51a24a8ea26a" alt="设为共享聊天" /></p>

4. 您的团队现在可以实时聊天。

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeChatGif.gif" alt="实时聊天" /></p>

5. 添加评论以标记队友。

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeCommentsFlow.gif" alt="实时评论" /></p>

## SurfSense vs Google NotebookLM

| 功能 | Google NotebookLM | SurfSense |
|---------|-------------------|-----------|
| **每个笔记本的来源数** | 50（免费）到 600（Ultra，$249.99/月） | 无限制 |
| **笔记本数量** | 100（免费）到 500（付费方案） | 无限制 |
| **来源大小限制** | 500,000 词 / 200MB 每个来源 | 无限制 |
| **定价** | 免费版可用；Pro $19.99/月，Ultra $249.99/月 | 免费开源，在自己的基础设施上自托管 |
| **LLM 支持** | 仅 Google Gemini | 100+ LLM，通过 OpenAI spec 和 LiteLLM |
| **嵌入模型** | 仅 Google | 6,000+ 嵌入模型，所有主流重排序器 |
| **本地 / 私有 LLM** | 不可用 | 完整支持（vLLM、Ollama）- 您的数据由您掌控 |
| **可自托管** | 否 | 是 - Docker 一行命令或完整 Docker Compose |
| **开源** | 否 | 是 |
| **外部连接器** | Google Drive、YouTube、网站 | 27+ 连接器 - 搜索引擎、Google Drive、OneDrive、Dropbox、Slack、Teams、Jira、Notion、GitHub、Discord 等[更多](#外部数据源) |
| **文件格式支持** | PDF、Docs、Slides、Sheets、CSV、Word、EPUB、图像、网页 URL、YouTube | 50+ 格式 - 文档、图像、视频，通过 LlamaCloud、Unstructured 或 Docling（本地） |
| **搜索** | 语义搜索 | 混合搜索 - 语义 + 全文搜索，结合层次化索引和倒数排名融合 |
| **引用回答** | 是 | 是 - Perplexity 风格的引用回答 |
| **代理架构** | 否 | 是 - 基于 [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) 构建，支持规划、子代理和文件系统访问 |
| **实时多人协作** | 共享笔记本，支持查看者/编辑者角色（无实时聊天） | RBAC 角色控制（所有者/管理员/编辑者/查看者），实时聊天和评论线程 |
| **视频生成** | 通过 Veo 3 的电影级视频概览（仅 Ultra） | 可用（NotebookLM 在此方面更好，正在积极改进） |
| **演示文稿生成** | 更美观的幻灯片但不可编辑 | 创建可编辑的幻灯片式演示文稿 |
| **播客生成** | 可自定义主持人和语言的音频概览 | 可用，支持多种 TTS 提供商（NotebookLM 在此方面更好，正在积极改进） |
| **桌面应用** | 否 | 原生应用，包含 General Assist、Quick Assist、Screenshot Assist 和本地文件夹同步 |
| **浏览器扩展** | 否 | 跨浏览器扩展，保存任何网页，包括需要身份验证的页面 |

<details>
<summary><b>外部数据源完整列表</b></summary>
<a id="外部数据源"></a>

搜索引擎（Tavily、LinkUp）· SearxNG · Google Drive · OneDrive · Dropbox · Slack · Microsoft Teams · Linear · Jira · ClickUp · Confluence · BookStack · Notion · Gmail · YouTube 视频 · GitHub · Discord · Airtable · Google Calendar · Luma · Circleback · Elasticsearch · Obsidian，更多即将推出。

</details>


## 功能请求与未来规划


**SurfSense 正在积极开发中。** 虽然它还未达到生产就绪状态，但您可以帮助我们加快进度。

加入 [SurfSense Discord](https://discord.gg/ejRNvftDp9) 一起塑造 SurfSense 的未来！

## 路线图

随时了解我们的开发进度和即将推出的功能！  
查看我们的公开路线图并贡献您的想法或反馈：

**路线图讨论：** [SurfSense 2026 Roadmap](https://github.com/MODSetter/SurfSense/discussions/565)

**看板：** [SurfSense Project Board](https://github.com/users/MODSetter/projects/3)


## 贡献

欢迎所有贡献，从 Star 和 Bug 报告到后端改进。请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 开始贡献。

感谢所有 Surfers:

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
