# Glossary

One term per concept, so the app says the same thing everywhere. Terms marked with † come from the per-language search data in [`03-international.md`](../../../plans/community-local/seo/03-international.md#glossaries), so the app matches the website. Add a row when a term will recur; change a row only with every key that uses it.

## Stays in English

SurfSense, Studio, llama.cpp, GGUF, Hugging Face, API, MCP, and every model and provider name.

`workspace` is the one product word languages disagree on, and each keeps its own habit: German and Brazilian Portuguese write Workspace, because both say it routinely and the translation is three times as wide in the sidebar; Japanese writes ワークスペース, since `マイWorkspace` reads as a mistake; the rest translate it.

## Per language

| Concept | Japanese | Korean | Simplified Chinese | Hindi | German | Spanish | French | Brazilian Portuguese | Russian |
|---|---|---|---|---|---|---|---|---|---|
| local LLM | ローカルLLM † | 로컬 LLM | 本地 LLM | लोकल LLM | lokales LLM † | LLM local | LLM local | LLM local | локальная LLM |
| local AI | ローカルAI † | 로컬 AI | 本地 AI | लोकल AI | lokale KI † | IA local | IA locale | IA local | локальный ИИ |
| offline | オフライン † | 오프라인 | 离线 | ऑफ़लाइन | offline † | sin conexión | hors ligne | offline | офлайн |
| open source | オープンソース † | 오픈소스 | 开源 | ओपन सोर्स | Open Source † | código abierto | open source | código aberto | открытый исходный код |
| privacy | プライバシー | 프라이버시 | 隐私 | गोपनीयता | Datenschutz † | privacidad | confidentialité | privacidade | конфиденциальность |
| source (an added file or folder) | ソース | 소스 | 来源 | स्रोत | Quelle | fuente | source | fonte | источник |
| document | ドキュメント | 문서 | 文档 | दस्तावेज़ | Dokument | documento | document | documento | документ |
| chat | チャット | 채팅 | 对话 | चैट | Chat | chat | chat | chat | чат |
| model | モデル | 모델 | 模型 | मॉडल | Modell | modelo | modèle | modelo | модель |
| download | ダウンロード † | 다운로드 | 下载 | डाउनलोड | herunterladen | descargar | télécharger | baixar | скачать |
| settings | 設定 | 설정 | 设置 | सेटिंग्स | Einstellungen | ajustes | Paramètres | Configurações | настройки |
| slides | スライド † | 슬라이드 | 幻灯片 | स्लाइड | Präsentation † | diapositivas | Présentation | Slides | Слайды |
| summary | 要約 † | 요약 | 摘要 | सारांश | Zusammenfassung † | resumen | Résumé | Resumo | Резюме |
| mind map | マインドマップ † | 마인드맵 | 思维导图 | माइंड मैप | Mindmap † | mapa mental | Carte mentale | Mapa mental | интеллект-карта |
| flashcards | フラッシュカード | 플래시카드 | 记忆卡片 | फ़्लैशकार्ड | Karteikarten † | tarjetas didácticas | Cartes mémoire | Flashcards | Карточки |
| quiz | クイズ | 퀴즈 | 测验 | क्विज़ | Quiz † | cuestionario | Quiz | Quiz | Тест |
| study guide | 学習ガイド | 학습 가이드 | 学习指南 | स्टडी गाइड | Lernzettel † | guía de estudio | Guide de révision | Guia de estudos | конспект |
| podcast | ポッドキャスト | 팟캐스트 | 播客 | पॉडकास्ट | Podcast | podcast | Podcast | Podcast | подкаст |
| workspace | ワークスペース | 워크스페이스 | 工作区 | वर्कस्पेस | Workspace | espacio de trabajo | espace de travail | Workspace | рабочая область |
| artifact (a Studio output) | 生成物 | 생성물 | 产物 | आर्टिफ़ैक्ट | Artefakt | artefacto | artefact | artefato | артефакт |
| chunk (a cited passage) | チャンク | 청크 | 片段 | चंक | Abschnitt | fragmento | extrait | trecho | фрагмент |
| citation | 引用 | 인용 | 引用 | उद्धरण | Quellenangabe | cita | citation | citação | цитата |
| Model setup | モデル設定 | 모델 설정 | 模型设置 | मॉडल सेटअप | Modell-Einrichtung | Ajustes del modelo | Configuration du modèle | Configuração de modelos | Настройка модели |
| vision (model badge) | 画像認識 | 이미지 인식 | 图像识别 | विज़न | Vision | Visión | Vision | Visão | Изображения |
| build (a quantized variant) | ビルド | 빌드 | 版本 | बिल्ड | Variante | variante | variante | variante | сборка |
| in use | 使用中 | 사용 중 | 使用中 | उपयोग में | Aktiv | En uso | Actif | Em uso | Используется |
| server (a model server) | サーバー | 서버 | 服务器 | सर्वर | Server | servidor | serveur | servidor | сервер |
| provider | プロバイダー | 제공업체 | 提供商 | प्रोवाइडर | Anbieter | proveedor | fournisseur | provedor | провайдер |
| this computer | このコンピューター | 이 컴퓨터 | 这台电脑 | यह कंप्यूटर | dieser Computer | este equipo | cet ordinateur | este computador | этот компьютер |
| retry | 再試行 | 다시 시도 | 重试 | फिर से कोशिश करें | Erneut versuchen | Reintentar | Réessayer | Tentar novamente | Повторить |
| View (menu) | 表示 | 보기 | 视图 | देखें | Darstellung | Ver | Affichage | Exibir | Вид |

## What the English means

Strings whose English is ambiguous enough that every translator so far had to open the component. Read these before translating them; a reworded English would retire the row.

| String | What it means |
|---|---|
| "priced against this computer" (`models_download_chat_curated_body`, `models_hardware_summary_body`) | the fit estimate for this hardware, never money. Nine languages landed on "estimated for this computer"; Chinese read it as resource cost. |
| "This build" (`models_download_*_unsupported_body`) | the **app** build the user installed, not the quantized variant the `build` row above covers, so it takes a different word. |
| "the brief" (`studio_composer_brief_status`) | the podcast brief the user just filled in, not a summary; keep the `summary` term free. |
| "Ingestion" (`sources_row_failed_status` and neighbours) | the parse-and-index pass. Match whatever `sources_row_processing_aria` says, so the pair reads as one pipeline. |
| "Model setup" (`chat_failed_reply_model_setup_button`) | the models section of Settings, which is where the button goes. Name it for that destination, and keep it short enough for a button. |
| "Clock is off" (`dashboard_footer_license_clock_status`) | the machine's clock is **wrong**, not switched off. |
| "Selecting" (`models_install_selecting_status`) | the install phase that makes the new model the active one, not the user picking anything. |
| "Needs review" / "Got it" (`studio_flashcards_viewer_again_button`, `_good_button`) | the two grades on a card. Reuse the exact words in the reset dialog, which quotes them. |
| "seats" (`license_status_seats_label`) | licensed users. |
