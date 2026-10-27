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

  <a href="https://www.surfsense.com/"><img alt="SurfSense。ネットワークから切り離して使える、オープンソースの NotebookLM 代替" src="www/public/homepage/banner.png" /></a>

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
    <a href="#プラグイン">プラグイン</a> ·
    <a href="https://www.surfsense.com/pricing">料金</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | 日本語 | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

**契約書に変更履歴とコメントで朱入れ**

https://github.com/user-attachments/assets/88326b9d-e763-46db-9635-75f9df9e8682

**ウェブからソースを追加して、Webページに仕上げる**

https://github.com/user-attachments/assets/073577b7-f055-4f59-8540-330bd764aeb0

SurfSense は、アップロードできない文書のための、無料のオープンソース・デスクトップアプリです。プライバシーを重視した NotebookLM のような AI エージェントが、手元の文書を自分のマシン上で調査し、変換し、編集します。索引は自分のディスクに残り、モデルはローカルでもリモートでも自分で選べます。アカウントも要りません。

| プラットフォーム | ダウンロード |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://www.surfsense.com/downloads/windows?src=readme) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://www.surfsense.com/downloads/mac?src=readme) |
| **Linux** x64 | [AppImage](https://www.surfsense.com/downloads/linux-appimage?src=readme) · [deb](https://www.surfsense.com/downloads/linux-deb?src=readme) |

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
| **録音** WAV、MP3、FLAC、Ogg Vorbis | ✓ 自分のマシン上で文字起こし | — | — | — |
| **ポッドキャスト**（音声） | — | ✓ 文字起こし付き。初期状態では自分のマシン上で読み上げる | — | — |
| **マインドマップ、フラッシュカード、クイズ** | — | ✓ アプリ内で | — | — |

<sub>¹ 設定で Officeサポート（LibreOffice）をオンにすると使えます。LibreOffice がインストーラーに含まれることはありません。² ローカルまたはリモートの画像モデルが必要です。初期状態ではどれも選ばれていません。³ OCR が読めるのは、ラテン文字、中国語、日本語の文字です。</sub>

編集、変換、PDF ツールは、いつも新しいファイルを作ります。元のファイルが変更されることはありません。現時点でいちばん多くのことができるのは PDF、Word、Excel で、ほかの形式への対応も改善を続けています。

## プラグイン

**設定 › プラグイン**で接続します。

**SurfSense提供。** 自分のアカウントを使わずに公開ページを読み取ります。利用には SurfSense ライセンスが必要です。[アプリをダウンロード](https://www.surfsense.com/downloads)し、アプリでメールアドレスを入力すると、14 日間の無料ライセンスを受け取れます。

| プラグイン | できること |
|---|---|
| **Google Search** | Google で検索し、検索結果、広告、関連する質問を読み取る |
| **Web Crawl** | Webページを読み取るか、サイト全体をクロールしてクリーンなテキストにする |
| **YouTube** | YouTube の動画、チャンネル、それらのコメントを読み取る |
| **TikTok** | TikTok の動画とそのコメントを読み取り、ユーザーを検索し、トレンドを確認する |
| **Reddit** | Reddit の公開投稿とそのコメントスレッド、またはコミュニティ全体を読み取る |
| **Instagram** | Instagram の公開プロフィール、投稿、リールを読み取り、プロフィールを検索する |
| **Google Maps** | Google Maps で場所を探し、そのレビューを読み取る |
| **Amazon** | Amazon の商品と検索結果を読み取る |
| **Walmart** | Walmart の商品、検索結果、レビューを読み取る |
| **Indeed** | Indeed の求人情報を読み取る |

**サードパーティ。** [プラグインレジストリ](backend/plugins/registry)にある DeepWiki や Notion などの MCP サーバーや、URL を指定して自分で追加したサーバーです。ライセンスは不要で、許可するまではオフのままです。

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

## ライセンス

Apache-2.0。[LICENSE](LICENSE) を参照してください。
