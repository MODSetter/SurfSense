<!--
  下线提示有时效：请在 2026 年 10 月 18 日删除它，并同时删除 README.md 中的同一条提示。
  本文件与 README.md 逐节对应。
  依据：plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img alt="SurfSense，可物理隔离运行的开源 NotebookLM 替代品" src="www/public/homepage/banner.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>可物理隔离运行的开源 NotebookLM 替代品。</b>
    <br />
    在你自己的电脑上研究、转换和编辑文档的 AI 智能体。
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>下载</b></a> ·
    <a href="#每种格式能做什么">格式</a> ·
    <a href="#快速开始">快速开始</a> ·
    <a href="#surfsense-与同类工具对比">对比</a> ·
    <a href="#插件">插件</a> ·
    <a href="https://www.surfsense.com/pricing">定价</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | 简体中文
  </p>
</div>

**用修订和批注批改合同**

https://github.com/user-attachments/assets/88326b9d-e763-46db-9635-75f9df9e8682

**从网上添加来源，再把它们做成网页**

https://github.com/user-attachments/assets/073577b7-f055-4f59-8540-330bd764aeb0

SurfSense 是一款免费开源的桌面应用，专为那些不能上传的文档而做。它是一个注重隐私、类似 NotebookLM 的 AI 智能体，在你自己的电脑上研究、转换和编辑你的文档。索引留在你的硬盘里，模型由你来选，本地或远程都可以，而且不需要账号。

| 平台 | 下载 |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://www.surfsense.com/downloads/windows?src=readme) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://www.surfsense.com/downloads/mac?src=readme) |
| **Linux** x64 | [AppImage](https://www.surfsense.com/downloads/linux-appimage?src=readme) · [deb](https://www.surfsense.com/downloads/linux-deb?src=readme) |

## 快速开始

1. 安装 SurfSense，完成初始设置。
2. 把文件或文件夹拖放到来源中。
3. 让智能体搜索、提取或编辑你的文件。

## 每种格式能做什么

| 格式 | 研究（带出处的回答） | 创建 | 编辑（以副本形式） | 转换 |
|---|---|---|---|---|
| **PDF** | ✓ 扫描页也可以³ | ✓ | 填写并拼合表单；添加水印、页码、页眉、页脚 | 合并、拆分、提取、旋转页面，调整页面顺序 |
| **Word** `.docx` | ✓ | ✓ 也可以用你自己的 `.docx` 作模板 | ✓ 正文，以修订和批注的形式 | 转为 PDF¹ |
| **Excel** `.xlsx` | ✓ 智能体还会读取公式 | ✓ 带公式和原生图表 | ✓ 单元格的值和公式 | 用 pandas 分析，并把结果做成图表 |
| **PowerPoint** `.pptx` | ✓ | ✓ 也可以用你自己的 `.pptx` 作模板 | 替换幻灯片和备注中的文字；删除或复制幻灯片 | 转为 PDF¹ |
| **CSV** | ✓ | — | — | 用 pandas 分析，并把结果做成图表 |
| **图像** PNG、JPEG、TIFF、BMP、WebP | ✓ 通过 OCR 识别其中的文字³ | 图像和信息图² | — | 放入新文档 |
| **Markdown**、纯文本 | ✓ | ✓ Markdown | — | — |
| **HTML** | ✓ | ✓ 网页 | — | — |
| **录音** WAV、MP3、FLAC、Ogg Vorbis | ✓ 在你的电脑上转写 | — | — | — |
| **播客**（音频） | — | ✓ 附文字稿，默认在你的电脑上配音 | — | — |
| **思维导图、记忆卡片、测验** | — | ✓ 在应用内 | — | — |

<sub>¹ 需要在设置中开启 Office 支持（LibreOffice）；安装程序中从不包含它。² 需要一个图像模型，本地或远程均可；默认不选择任何模型。³ OCR 可识别拉丁字母、中文和日文。</sub>

编辑、转换和 PDF 工具总是生成一个新文件，你的原文件永远不会被改动。目前 PDF、Word 和 Excel 能做的事最多，对其他格式的支持也在不断改进。

## 插件

在**设置 › 插件**中连接它们。

**SurfSense 提供：** 这些插件读取公开网页，不需要你自己的账号，但需要 SurfSense 许可证。[下载应用](https://www.surfsense.com/downloads)并在应用里填写你的邮箱，即可免费获得 14 天的许可证。

| 插件 | 功能 |
|---|---|
| **Google Search** | 在 Google 上搜索，并读取搜索结果、广告和相关问题 |
| **Web Crawl** | 读取单个网页，或把整个网站抓取为干净的文本 |
| **YouTube** | 读取 YouTube 视频、频道及其评论 |
| **TikTok** | 读取 TikTok 视频及其评论，搜索用户，查看当前的热门内容 |
| **Reddit** | 读取 Reddit 的公开帖子及其评论串，或整个社区 |
| **Instagram** | 读取 Instagram 的公开主页、帖子和 Reels，并搜索主页 |
| **Google Maps** | 在 Google Maps 上查找地点，并读取这些地点的评价 |
| **Amazon** | 读取 Amazon 商品和搜索结果 |
| **Walmart** | 读取 Walmart 商品、搜索结果和评价 |
| **Indeed** | 读取 Indeed 上的职位信息 |

**第三方：** 来自[插件注册表](backend/plugins/registry)的 MCP 服务器，例如 DeepWiki 和 Notion，或者你通过网址添加的任意服务器。不需要许可证；在你允许之前，它们一直保持关闭。

## SurfSense 与同类工具对比

| | NotebookLM（现为 Gemini Notebook） | SurfSense |
|---|---|---|
| 可离线 / 物理隔离运行 | 否 | **是** |
| 文档会离开你的电脑 | 会 | **不会**，除非你选择远程模型 |
| 能编辑你的文件 | 否 | **是** |
| 开源 | 否 | **Apache-2.0** |
| 模型 | 只能用 Gemini | 任意兼容 OpenAI 的 API，或本地模型 |

## 社区

- [Discord](https://discord.gg/ejRNvftDp9) 用来求助，[Issues](https://github.com/MODSetter/SurfSense/issues) 用来报告缺陷，[Discussions](https://github.com/MODSetter/SurfSense/discussions) 用来交流想法。
- **参与贡献：** PR 请提交到 `dev` 分支；开发流程见 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [`surfsense_local/`](./surfsense_local)。工作原理见 [`docs/`](docs/README.md)。

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors"><img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="为 SurfSense 做出贡献的人" /></a>

## 许可证

Apache-2.0。详见 [LICENSE](LICENSE)。
