<!--
  提供終了の注記は期限付き。2026 年 10 月 18 日に、README.md の同じ注記と一緒に削除する。
  このファイルは README.md と節ごとに対応する。
  根拠: plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img alt="SurfSense。ネットワークから切り離して使える、オープンソースの NotebookLM 代替" src="surfsense_web/public/homepage/banner.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>ネットワークから切り離して使える、オープンソースの NotebookLM 代替。</b>
    <br />
    自分のマシン上で、手元の文書を調査し、変換し、編集する AI エージェント。
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>ダウンロード</b></a> ·
    <a href="#形式ごとにできること">形式</a> ·
    <a href="#クイックスタート">クイックスタート</a> ·
    <a href="#surfsenseの比較">比較</a> ·
    <a href="https://www.surfsense.com/pricing">料金</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | 日本語 | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

https://github.com/user-attachments/assets/88326b9d-e763-46db-9635-75f9df9e8682

SurfSense は、アップロードできない文書のための、無料のオープンソース・デスクトップアプリです。プライバシーを重視した NotebookLM のような AI エージェントが、手元の文書を自分のマシン上で調査し、変換し、編集します。索引は自分のディスクに残り、モデルはローカルでもリモートでも自分で選べます。アカウントも要りません。

| プラットフォーム | ダウンロード |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-Setup.exe) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-arm64.dmg) |
| **Linux** x64 | [AppImage](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.AppImage) · [deb](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.deb) |

> [!NOTE]
> **ホスト版の Web アプリを使っていましたか？** 2026 年 10 月 18 日より前にワークスペースをエクスポートし、こちらにインポートしてください。詳細は[提供終了のページ](https://www.surfsense.com/sunset)をご覧ください。

## クイックスタート

1. SurfSense をインストールし、最初のセットアップを済ませます。
2. ファイルやフォルダーをソースにドロップします。
3. ファイルの検索、抽出、編集をエージェントに頼みます。

## 形式ごとにできること

| 形式 | 調査（出典付きの回答） | 作成 | 編集（コピーとして） | 変換 |
|---|---|---|---|---|
| **PDF** | ✓ スキャンしたページも³ | ✓ | フォームの入力とフラット化。透かし、ページ番号、ヘッダー、フッターの追加 | ページの結合、分割、抽出、回転、並べ替え |
| **Word** `.docx` | ✓ | ✓ 自分の `.docx` をテンプレートにすることも可能 | ✓ 本文を、変更履歴とコメントの形で | PDF へ¹ |
| **Excel** `.xlsx` | ✓ エージェントは数式も読み取る | ✓ 数式とネイティブのグラフ付き | ✓ セルの値と数式 | pandas で分析し、結果をグラフにする |
| **PowerPoint** `.pptx` | ✓ | ✓ 自分の `.pptx` をテンプレートにすることも可能 | スライドとノートのテキストを置換。スライドの削除や複製 | PDF へ¹ |
| **CSV** | ✓ | — | — | pandas で分析し、結果をグラフにする |
| **画像** PNG、JPEG、TIFF、BMP、WebP | ✓ 文字は OCR で読み取る³ | 画像とインフォグラフィック² | — | 新しい文書に配置する |
| **Markdown**、プレーンテキスト | ✓ | ✓ Markdown | — | — |
| **HTML** | ✓ | ✓ Webページ | — | — |
| **ポッドキャスト**（音声） | — | ✓ 文字起こし付き。初期状態では自分のマシン上で読み上げる | — | — |
| **マインドマップ、フラッシュカード、クイズ** | — | ✓ アプリ内で | — | — |

<sub>¹ 設定で Officeサポート（LibreOffice）をオンにすると使えます。LibreOffice がインストーラーに含まれることはありません。² ローカルまたはリモートの画像モデルが必要です。初期状態ではどれも選ばれていません。³ OCR が読めるのは、ラテン文字、中国語、日本語の文字です。</sub>

編集、変換、PDF ツールは、いつも新しいファイルを作ります。元のファイルが変更されることはありません。現時点でいちばん多くのことができるのは PDF、Word、Excel で、ほかの形式への対応も改善を続けています。

## SurfSenseの比較

| | NotebookLM（現 Gemini Notebook） | SurfSense |
|---|---|---|
| オフライン / ネットワーク分離で動く | いいえ | **はい** |
| 文書が自分のマシンの外に出る | 出る | **出ない**（リモートモデルを選んだ場合を除く） |
| ファイルを編集できる | いいえ | **はい** |
| オープンソース | いいえ | **Apache-2.0** |
| モデル | Gemini のみ | OpenAI 互換の任意の API、またはローカルモデル |

## コミュニティ

- 困ったときは [Discord](https://discord.gg/ejRNvftDp9)、不具合は [Issues](https://github.com/MODSetter/SurfSense/issues)、アイデアは [Discussions](https://github.com/MODSetter/SurfSense/discussions) へ。
- **開発への参加：** PR は `dev` に向けて出してください。開発の流れは [CONTRIBUTING.md](CONTRIBUTING.md) と [`surfsense_local/`](./surfsense_local) にあります。仕組みの説明は [`docs/`](docs/README.md) にあります。

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors"><img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="SurfSense のコントリビューター" /></a>

## スター履歴

<p align="center">
  <a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
    </picture>
  </a>
</p>

## ライセンス

Apache-2.0。[LICENSE](LICENSE) を参照してください。
