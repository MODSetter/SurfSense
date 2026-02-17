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
将任何 LLM 连接到您的内部知识源，并与团队成员实时聊天。NotebookLM、Perplexity 和 Glean 的开源替代方案。

SurfSense 是一个高度可定制的 AI 研究助手，可以连接外部数据源，如搜索引擎（SearxNG、Tavily、LinkUp）、Google Drive、Slack、Microsoft Teams、Linear、Jira、ClickUp、Confluence、BookStack、Gmail、Notion、YouTube、GitHub、Discord、Airtable、Google Calendar、Luma、Circleback、Elasticsearch、Obsidian 等，未来还会支持更多。



# 视频 

https://github.com/user-attachments/assets/cc0c84d3-1f2f-4f7a-b519-2ecce22310b1

## 播客示例

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7


## 如何使用 SurfSense

### Cloud

1. 访问 [surfsense.com](https://www.surfsense.com) 并登录。

<p align="center"><img src="https://github.com/user-attachments/assets/b4df25fe-db5a-43c2-9462-b75cf7f1b707" alt="登录" /></p>

2. 连接您的连接器并同步。启用定期同步以保持连接器数据更新。

<p align="center"><img src="https://github.com/user-attachments/assets/59da61d7-da05-4576-b7c0-dbc09f5985e8" alt="连接器" /></p>

3. 在连接器数据索引期间，上传文档。

<p align="center"><img src="https://github.com/user-attachments/assets/d1e8b2e2-9eac-41d8-bdc0-f0cdc405d128" alt="上传文档" /></p>

4. 一切索引完成后，尽管提问（使用场景）：

   - 基本搜索和引用

   <p align="center"><img src="https://github.com/user-attachments/assets/81e797a1-e01a-4003-8e60-0a0b3a9789df" alt="搜索和引用" /></p>

   - 文档提及问答

   <p align="center"><img src="https://github.com/user-attachments/assets/be958295-0a8c-4707-998c-9fe1f1c007be" alt="文档提及问答" /></p>

   - 报告生成和导出（目前支持 PDF、DOCX）

   <p align="center"><img src="https://github.com/user-attachments/assets/9836b7d6-57c9-4951-b61c-68202c9b6ace" alt="报告生成" /></p>

   - 播客生成

   <p align="center"><img src="https://github.com/user-attachments/assets/58c9b057-8848-4e81-aaba-d2c617985d8c" alt="播客生成" /></p>

   - 图像生成

   <p align="center"><img src="https://github.com/user-attachments/assets/25f94cb3-18f8-4854-afd9-27b7bfd079cb" alt="图像生成" /></p>

   - 更多功能即将推出。


### 自托管

在您自己的基础设施上运行 SurfSense，实现完全的数据控制和隐私保护。

**快速开始（Docker 一行命令）：**

```bash
docker run -d -p 3000:3000 -p 8000:8000 -p 5133:5133 -v surfsense-data:/data --name surfsense --restart unless-stopped ghcr.io/modsetter/surfsense:latest
```

启动后，在浏览器中打开 [http://localhost:3000](http://localhost:3000)。

如需 Docker Compose、手动安装及其他部署方式，请查看[文档](https://www.surfsense.com/docs/)。

### 如何实时协作（Beta）

1. 前往成员管理页面并创建邀请。

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="邀请成员" /></p>

2. 队友加入后，该 SearchSpace 变为共享。

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="邀请加入流程" /></p>

3. 将聊天设为共享。

   <p align="center"><img src="https://github.com/user-attachments/assets/17b93904-0888-4c3a-ac12-51a24a8ea26a" alt="设为共享聊天" /></p>

4. 您的团队现在可以实时聊天。

   <p align="center"><img src="https://github.com/user-attachments/assets/83803ac2-fbce-4d93-aae3-85eb85a3053a" alt="实时聊天" /></p>

5. 添加评论以标记队友。

   <p align="center"><img src="https://github.com/user-attachments/assets/3b04477d-8f42-4baa-be95-867c1eaeba87" alt="实时评论" /></p>

## 核心功能

| 功能 | 描述 |
|------|------|
| 开源替代方案 | 支持实时团队协作的 NotebookLM、Perplexity 和 Glean 替代品 |
| 50+ 文件格式 | 通过 LlamaCloud、Unstructured 或 Docling（本地）上传文档、图像、视频 |
| 混合搜索 | 语义搜索 + 全文搜索，结合层次化索引和倒数排名融合 |
| 引用回答 | 与知识库对话，获得 Perplexity 风格的引用回答 |
| 深度代理架构 | 基于 [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) 构建，支持规划、子代理和文件系统访问 |
| 通用 LLM 支持 | 100+ LLM、6000+ 嵌入模型、所有主流重排序器，通过 OpenAI spec 和 LiteLLM |
| 隐私优先 | 完整本地 LLM 支持（vLLM、Ollama），您的数据由您掌控 |
| 团队协作 | RBAC 角色控制（所有者/管理员/编辑者/查看者），实时聊天和评论线程 |
| 播客生成 | 20 秒内生成 3 分钟播客；多种 TTS 提供商（OpenAI、Azure、Kokoro） |
| 浏览器扩展 | 跨浏览器扩展，保存任何网页，包括需要身份验证的页面 |
| 25+ 连接器 | 搜索引擎、Google Drive、Slack、Teams、Jira、Notion、GitHub、Discord 等[更多](#外部数据源) |
| 可自托管 | 开源，Docker 一行命令或完整 Docker Compose 用于生产环境 |

<details>
<summary><b>外部数据源完整列表</b></summary>
<a id="外部数据源"></a>

搜索引擎（Tavily、LinkUp）· SearxNG · Google Drive · Slack · Microsoft Teams · Linear · Jira · ClickUp · Confluence · BookStack · Notion · Gmail · YouTube 视频 · GitHub · Discord · Airtable · Google Calendar · Luma · Circleback · Elasticsearch · Obsidian，更多即将推出。

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
