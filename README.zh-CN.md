<!--
  下线提示有时效。请在 2026 年 10 月 18 日导出窗口关闭时删除它，
  以及下文中“从托管版应用导入”那条链接。
  本文件与 README.md 逐节对应，改动请同步。
  本页文案依据：plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Forks](https://img.shields.io/github/forks/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/network/members)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img width="128" height="128" alt="SurfSense，可物理隔离运行的开源 NotebookLM 替代品" src="surfsense_web/public/homepage/icon.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>可物理隔离运行的开源 NotebookLM 替代品。</b>
    <br />
    把那些不能上传的文档，在你自己的电脑上变成简报、幻灯片、报告、学习指南和播客。
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>下载</b></a> ·
    <a href="https://www.surfsense.com/docs">文档</a> ·
    <a href="#surfsense-能生成什么">它能生成什么</a> ·
    <a href="#surfsense-与同类工具对比">对比</a> ·
    <a href="https://www.surfsense.com/pricing">定价</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | 简体中文
  </p>
</div>

<p align="center">
  <img src="surfsense_web/public/homepage/offline-studio.png" alt="SurfSense 桌面应用，已打开 Studio 并选中 Qwen，正在把本地来源变成成品" />
</p>

SurfSense 是一款免费开源的桌面应用，专为你手头已有的文档而做。把文档拖进来提问，得到的答案都会标注出处；同一批文档还能直接变成简报、幻灯片、报告、学习指南或播客。这一切都在你自己的电脑上完成：索引存在你的硬盘里，模型由你来选，应用不上传任何东西。也不需要注册账号。

**开始使用。**下载适合你系统的安装程序，然后自带模型密钥，或者让应用替你下载一个本地模型。

| 平台 | 下载 |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-Setup.exe) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-arm64.dmg) |
| **Linux** x64 (AppImage) | [SurfSense.AppImage](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.AppImage) |
| **Linux** x64 (deb) | [SurfSense.deb](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.deb) |

每个链接都是指向最新版本的永久链接。你也可以到 [surfsense.com/downloads](https://www.surfsense.com/downloads) 挑选，或浏览[全部版本](https://github.com/MODSetter/SurfSense/releases)。AppImage 会自动更新，deb 不会。

> [!NOTE]
> **用过托管版 Web 应用？**它即将下线。打开它一次，导出你的工作区，再把导出包导入桌面应用；文档、文件夹、标题和对话记录都会一并迁移过来。导出窗口将于 2026 年 10 月 18 日关闭。详见[下线说明页](https://www.surfsense.com/sunset)。

## SurfSense 能生成什么

选几份文档，再选一种格式。应用就会在你的电脑上，用你挑的来源把它写出来。

| 格式 | 你会得到什么 | 需要 |
|---|---|---|
| **摘要** | 针对所选来源的结构化简报 | 生成模型 |
| **闪卡** | 一套可交互的卡片，一次一张 | 生成模型 |
| **测验** | 带答案的选择题 | 生成模型 |
| **思维导图** | 可缩放、可折叠的 Markmap | 生成模型 |
| **幻灯片** | 可编辑的 `.pptx`，不是一张幻灯片截图 | 生成模型 |
| **文档** | 可编辑的 `.docx` 报告 | 生成模型 |
| **电子表格** | 由来源中的表格汇成的 `.xlsx` | 生成模型 |
| **网页** | 一个自包含的 HTML 页面 | 生成模型 |
| **PDF** | 一份排好版的 PDF | 生成模型 |
| **播客** | 双主持人对谈音频，由 Kokoro-82M 离线配音 | 生成模型 + 音频模型 |
| **图片** | 为材料配的插图 | 图像模型 + 生成模型 |
| **信息图** | 单张图的可视化摘要 | 图像模型 + 生成模型 |

有些活儿不止用一种格式。一份学习指南，就是对同一批来源做的摘要、闪卡和测验；一份客户简报，通常是你上台讲的幻灯片，加上会后发过去的摘要。视频概览还没做。

## 一切都留在你的电脑上

大家会用它来处理案卷、客户工作底稿、访谈记录、内部规格文档、未发表的研究，以及一整个学期的课堂笔记。你可以对这些材料统一提问，每个答案都会标注它出自哪份来源。应用不会把其中任何内容上传出去。

- **索引在本地。**解析、切分和向量化都在你的电脑上完成，写入 `~/.surfsense` 下的 SQLite。SurfSense 不留副本，也不记录你问过什么。
- **每个环节都能本地运行。**文档解析器、检索模型和播客语音都随安装程序一起分发。对话和图像生成以本地服务的形式提供，权重只需下载一次，所以不用账号、不用 API 密钥也能产出文字、音频和图片。我们的验证方式是：断网导入一份 PDF。
- **对外连接默认关闭。**出站面板会列出应用可以访问的每一个目标地址，你想开哪个就开哪个。
- **没有遥测，没有崩溃上报。**没有任何东西回传，所以也不用去找哪里能关掉。

SurfSense 无法告诉你这是否满足某项具体的合规要求，那取决于你自己的管控措施和你的监管方。应用唯一能告诉你的，是你的文档在哪台机器上。

## SurfSense 与同类工具对比

有三类产品都被称作“本地版 NotebookLM”，但它们回答的是不同的问题。它们都不是坏工具，只是最后留给你的东西不一样。

**对比 Jan、AnythingLLM、Open WebUI、LM Studio。**它们在本地跑起一个模型，给你一个和它对话的地方。SurfSense 回答的是下一个问题：怎么从模型里拿到一份成品文档？你也可以两者搭配使用——把 SurfSense 指向任意兼容 OpenAI 的接口，包括它们提供的接口。

**对比 RemNote、Quizlet、NoteGPT、StudyFetch、Gamma。**它们确实能产出成品，有些还比我们做得好看。代价在于你的材料去了哪里：你得上传，按月付费，文件存放在别人的账号里。

**对比 Google NotebookLM。**它已经有闪卡、测验、思维导图和音频概览，两者产出的东西其实相当接近。区别在于活儿是在谁的机器上干的，以及你能给它接什么模型。

| | Google NotebookLM | SurfSense |
|---|---|---|
| 可离线 / 物理隔离运行 | 否 | **是** |
| 文档会离开你的电脑 | 会 | **不会** |
| 需要账号 | Google 账号 | **不需要** |
| 开源 | 否 | **Apache-2.0** |
| 价格 | 免费档；Pro 每月 $19.99；Ultra 每月 $249.99 | **应用免费** |
| 模型 | 只能用 Gemini | 任意兼容 OpenAI 的 API，或本地模型 |
| 来源数量上限 | 50 到 600 个来源，每个 50 万字 | 硬盘装得下就行 |
| 音频和视频概览 | 都有，而且更好 | 音频有，可离线；视频暂无 |

音频质量上 NotebookLM 更胜一筹，而且它有视频。如果你不介意自己的来源放在 Google 的服务器上，那就用它。如果你介意，SurfSense 就是同一类工具，只是不用上传。

## 快速开始

不需要 Docker，不需要命令行，不需要 GPU，也不需要 compose 文件。

1. **下载安装程序**，就在上面的表格里。安装包已签名，系统不会拦你。
2. **选一个模型。**可以让应用替你下载本地模型（Qwen3 共六种尺寸，最小 0.5 GB），也可以粘贴任意兼容 OpenAI 的 API 的 base URL 和密钥。模型选择器会先确认你的机器跑得动，再把模型列出来；你填的密钥都会加密保存，密钥本身存放在系统钥匙串里。
3. **把文档拖进来。**应用会在你的电脑上解析 PDF、Office 文件和图片。
4. **提问。**每个答案都会标注它出自哪份来源。
5. **打开 Studio，**选一种格式，取走文件。

慢的是下载这一步，因为安装程序里装着解析器、检索模型、播客语音和本地模型服务，这样应用在断网状态下也能用。

## 文档与社区

应用及其更新都是免费的。许可证增加的是插件和优先支持，除此之外不锁任何功能，所以许可证到期后，应用和今后的每一次更新依然归你。详见[定价](https://www.surfsense.com/pricing)。

本仓库里的 Docker 技术栈（`surfsense_backend`、`surfsense_web` 以及 compose 文件）继续开源、继续可安装，并且**由社区维护：没有 SLA，背后也没有托管服务。**新用户请走桌面应用这条受支持的路径。

- [文档](https://www.surfsense.com/docs)：安装、模型、Studio 格式与自托管
- [从托管版应用导入](https://www.surfsense.com/sunset)
- [MCP 服务器](./surfsense_mcp)：对接托管版抓取 API
- [Discord](https://discord.gg/ejRNvftDp9) 用来求助和交流想法，[Discussions](https://github.com/MODSetter/SurfSense/discussions) 用来讨论方向，[Issues](https://github.com/MODSetter/SurfSense/issues) 用来提可复现的缺陷
- **给仓库点个 Star**，就能跟进它之后的走向

## 参与贡献

欢迎提交 Pull Request，[CONTRIBUTING.md](CONTRIBUTING.md) 讲了完整流程。简单来说：

- **找一件事来做**：带有 [`good first issue`](https://github.com/MODSetter/SurfSense/labels/good%20first%20issue) 或 [`help wanted`](https://github.com/MODSetter/SurfSense/labels/help%20wanted) 标签的 issue，或者 [`docs/architecture/`](docs/architecture/overview.md) 里每篇文档末尾 Known gaps（已知缺口）列表中的一条。
- **先读懂它怎么工作**：[`docs/`](docs/README.md) 解释了每个功能以及它为什么这样实现，[`docs/ROADMAP.md`](docs/ROADMAP.md) 列出了维护者正在做的事。
- **向 `dev` 分支提交 PR**。修复缺陷和改文档不需要事先讨论；新功能先写一份简短的设计提案。桌面应用在 [`surfsense_local/`](./surfsense_local)，它的 README 讲了开发流程。

感谢所有 Surfer：

<p align="center">
  <a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="为 SurfSense 做出贡献的人" />
  </a>
</p>

## Star 历史

<p align="center">
  <a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
    </picture>
  </a>
</p>

## 许可证

Apache-2.0。详见 [LICENSE](LICENSE)。
