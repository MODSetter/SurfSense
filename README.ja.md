<!--
  提供終了の注記には期限がある。書き出し期間が閉じる 2026 年 10 月 18 日に、
  この注記と、下にある「ホスト版アプリから読み込む」リンクを削除する。
  このファイルは README.md と節ごとに対応する。
  このページの根拠: plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Forks](https://img.shields.io/github/forks/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/network/members)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img width="128" height="128" alt="SurfSense。ネットワークから切り離して使える、オープンソースの NotebookLM 代替" src="surfsense_web/public/homepage/icon.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>ネットワークから切り離して使える、オープンソースの NotebookLM 代替。</b>
    <br />
    アップロードできない文書を、ブリーフィング、スライド、レポート、学習ガイド、ポッドキャストに。すべて自分のマシン上で。
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>ダウンロード</b></a> ·
    <a href="https://www.surfsense.com/docs">ドキュメント</a> ·
    <a href="#surfsenseで作れるもの">作れるもの</a> ·
    <a href="#surfsenseの比較">比較</a> ·
    <a href="https://www.surfsense.com/pricing">料金</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | 日本語 | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

<p align="center">
  <img src="surfsense_web/public/homepage/offline-studio.png" alt="Studio を開き Qwen を選んだ SurfSense デスクトップアプリ。手元の資料から成果物を作っている" />
</p>

SurfSense は、すでに持っている文書のための、無料のオープンソース・デスクトップアプリです。ドロップして質問すると、出典を付けた答えが返ります。同じ文書から、ブリーフィング、スライド、レポート、学習ガイド、ポッドキャストも作れます。処理はすべて自分のマシンで行われます。索引はディスク上にあり、モデルは自分で選び、アプリは何もアップロードしません。アカウントも要りません。

**はじめに。**自分のマシン用のインストーラーを入手し、手元のモデルキーを入れるか、アプリにローカルモデルを取ってきてもらいます。

| プラットフォーム | ダウンロード |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-Setup.exe) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-arm64.dmg) |
| **Linux** x64 (AppImage) | [SurfSense.AppImage](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.AppImage) |
| **Linux** x64 (deb) | [SurfSense.deb](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.deb) |

どのリンクも、常に最新リリースを指します。[surfsense.com/downloads](https://www.surfsense.com/downloads) から選ぶことも、[すべてのリリース](https://github.com/MODSetter/SurfSense/releases)を見ることもできます。AppImage は自動更新します。deb はしません。

> [!NOTE]
> **ホスト版の Web アプリを使っていましたか？** 提供を終了します。一度開いてワークスペースを書き出し、その束をデスクトップアプリに読み込んでください。文書、フォルダ、タイトル、チャットのスレッドがまとめて移ります。書き出し期間は 2026 年 10 月 18 日に閉じます。詳細は[提供終了のページ](https://www.surfsense.com/sunset)にあります。

## SurfSenseで作れるもの

文書をいくつか選び、形式を選びます。アプリは、選んだ資料から、自分のマシン上でそれを書きます。

| 形式 | 得られるもの | 必要なもの |
|---|---|---|
| **要約** | 選んだ資料の構造化されたブリーフ | 生成モデル |
| **フラッシュカード** | 1 枚ずつめくる対話式のデッキ | 生成モデル |
| **クイズ** | 解答付きの選択式問題 | 生成モデル |
| **マインドマップ** | 拡大でき、折りたためる Markmap | 生成モデル |
| **スライド** | 編集できる `.pptx`。デッキの画像ではない | 生成モデル |
| **文書** | 編集できる `.docx` のレポート | 生成モデル |
| **スプレッドシート** | 資料から取り出した表の `.xlsx` | 生成モデル |
| **Web ページ** | 単体で完結する HTML ページ | 生成モデル |
| **PDF** | 組版された PDF | 生成モデル |
| **ポッドキャスト** | 二者の音声対話。Kokoro-82M がオフラインで読み上げる | 生成モデル + 同梱の音声 |
| **画像** | 資料のための図版 | 画像モデル + 生成モデル |
| **インフォグラフィック** | 1 枚の視覚的な要約 | 画像モデル + 生成モデル |

仕事によっては、形式が一つでは足りません。学習ガイドは、同じ資料に対する要約、フラッシュカード、クイズです。顧客向けブリーフィングは、たいてい、発表に使うデッキと、そのあと送る要約の組です。動画の概要はまだありません。

## すべては自分のマシンに残る

事件記録、顧客の作業文書、インタビューの書き起こし、社内仕様、未発表の研究、学期分の講義ノート。そうした資料に向けて使われています。全体に質問でき、どの答えも出自の資料を示します。アプリはそのどれもアップロードしません。

- **索引はローカルです。** 解析、分割、埋め込みは自分のコンピュータ上で行われ、`~/.surfsense` 配下の SQLite に入ります。SurfSense はその複製を持たず、何を質問したかの記録も残しません。
- **どの役割もローカルで動かせます。** 文書パーサー、検索モデル、ポッドキャストの音声はインストーラーに入っています。チャットと画像生成はローカルサーバーとして入り、重みは一度ダウンロードすれば足ります。アカウントも API キーもなく、文章、音声、画像を作れます。確認方法は、ネットワークを切った状態で PDF を取り込むことです。
- **外向きの接続は、初期状態ではオフです。** 通信先パネルが、アプリが到達できる宛先をすべて列挙します。使うものだけをオンにします。
- **テレメトリも、クラッシュ報告もありません。** 何も外部に送信しないので、オプトアウトを探す必要もありません。

これが特定の規制を満たすかどうかは、SurfSense からは答えられません。それは自分の管理策と、所管の規制当局によります。アプリが言えるのは、文書がどのマシンにあるかだけです。

## SurfSenseの比較

「ローカル版 NotebookLM」と呼ばれる製品は三種類あり、答えている問いが違います。どれも悪い道具ではありません。手元に残るものが違うだけです。

**Jan、AnythingLLM、Open WebUI、LM Studio と比べて。** これらはモデルをローカルで動かし、それと話す場所をくれます。SurfSense が答えるのは、その次の問いです。そこから完成した文書をどう取り出すか。併用もできます。SurfSense を、OpenAI 互換の任意のエンドポイント（それらの製品が提供するものを含む）に向ければ足ります。

**RemNote、Quizlet、NoteGPT、StudyFetch、Gamma と比べて。** これらは成果物を作り、見た目がこちらのものより良いものもあります。引き換えに、資料の置き場所が変わります。アップロードし、月額を払い、ファイルは他人のアカウントに置かれます。

**Google NotebookLM と比べて。** あちらにはすでにフラッシュカード、クイズ、マインドマップ、音声概要があります。作れるものは、おおむね同じです。違うのは、作業をするマシンが誰のものかと、どのモデルを向けられるかです。

| | Google NotebookLM | SurfSense |
|---|---|---|
| オフライン / ネットワーク分離で動く | いいえ | **はい** |
| 文書が自分のマシンの外に出る | 出る | **出ない** |
| アカウント | Google アカウントが必要 | **不要** |
| オープンソース | いいえ | **Apache-2.0** |
| 料金 | 無料枠。Pro は月額 $19.99。Ultra は月額 $249.99 | **アプリは無料** |
| モデル | Gemini のみ | OpenAI 互換の任意の API、またはローカルモデル |
| 資料の上限 | 50 から 600 件、各 50 万語 | ディスクに入るだけ |
| 音声と動画の概要 | あり。品質は上 | 音声はあり、オフライン。動画はまだない |

音声の品質では NotebookLM が上で、動画もあります。資料が Google のサーバーに置かれてよいなら、あちらを使ってください。そうでないなら、こちらはアップロードのない、同じ種類の道具です。

## クイックスタート

Docker も、ターミナルも、GPU も、compose ファイルも要りません。

1. **インストーラーを入手する。** 上の表から。署名されているので、OS は邪魔しません。
2. **モデルを選ぶ。** ローカルモデルをアプリに取ってきてもらう（Qwen3 は 6 サイズ、最小 0.5 GB）か、OpenAI 互換 API のベース URL とキーを貼ります。選択画面は、マシンで動かせることを確認してからモデルを出します。渡したキーは暗号化して保存され、秘密は OS のキーチェーンに入ります。
3. **文書を入れる。** PDF、Office ファイル、画像は、自分のマシン上で解析されます。
4. **質問する。** どの答えも、出自の資料を示します。
5. **Studio を開き、**形式を選び、ファイルを受け取る。

遅いのはダウンロードです。インストーラーがパーサー、検索モデル、ポッドキャスト音声、ローカルモデルサーバーを同梱しているためです。だからネットワークを切ってもアプリは動きます。

## ドキュメントとコミュニティ

アプリとその更新は無料です。ライセンスが足すのはプラグインと優先サポートだけで、それ以外は何も止めません。期限が切れても、アプリと今後の更新はそのまま残ります。[料金](https://www.surfsense.com/pricing)を参照してください。

このリポジトリの Docker スタック（`surfsense_backend`、`surfsense_web`、compose ファイル）はオープンソースのままインストールでき、**コミュニティによるサポートです。SLA はなく、背後にホスト型サービスもありません。** 新規の利用者にとって、サポートされる経路はデスクトップアプリです。

- [ドキュメント](https://www.surfsense.com/docs)。インストール、モデル、Studio の形式、セルフホスト
- [ホスト版アプリから読み込む](https://www.surfsense.com/sunset)
- ホスト版スクレイパー API のための [MCP サーバー](./surfsense_mcp)
- 助けとアイデアは [Discord](https://discord.gg/ejRNvftDp9)、方向性は [Discussions](https://github.com/MODSetter/SurfSense/discussions)、再現できる不具合は [Issues](https://github.com/MODSetter/SurfSense/issues)
- この先を追うなら、**リポジトリにスターを付けてください**

## 開発に参加する

プルリクエストを歓迎します。流れの全体は [CONTRIBUTING.md](CONTRIBUTING.md) にあります。短く言うと次のとおりです。

- **取り組むものを見つける。** [`good first issue`](https://github.com/MODSetter/SurfSense/labels/good%20first%20issue) または [`help wanted`](https://github.com/MODSetter/SurfSense/labels/help%20wanted) のラベルが付いた issue、あるいは [`docs/architecture/`](docs/architecture/overview.md) の各文書末尾にある Known gaps（既知の欠け）の一行。
- **先に仕組みを読む。** [`docs/`](docs/README.md) が各機能と、なぜそう作られているかを説明し、[`docs/ROADMAP.md`](docs/ROADMAP.md) がメンテナーの作業中のものを示します。
- **`dev` に対して PR を開く。** 不具合修正とドキュメントは、事前の議論が要りません。新機能は短い設計提案から始めます。デスクトップアプリは [`surfsense_local/`](./surfsense_local) にあり、その README が開発の一周を説明します。

Surfers の皆さんに感謝します。

<p align="center">
  <a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="SurfSense のコントリビューター" />
  </a>
</p>

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

Apache-2.0。 [LICENSE](LICENSE) を参照してください。
