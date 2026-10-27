<!--
  Пометка о закрытии ограничена по времени: удалите её 18 октября 2026 года
  вместе с такой же пометкой в README.md. Этот файл повторяет README.md раздел за разделом.
  Обоснование: plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img alt="SurfSense, изолированная от сети альтернатива NotebookLM с открытым кодом" src="www/public/homepage/banner.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>Изолированная от сети альтернатива NotebookLM с открытым кодом.</b>
    <br />
    ИИ-агент, который исследует, преобразует и редактирует документы прямо на вашем компьютере.
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>Скачать</b></a> ·
    <a href="#что-surfsense-делает-с-каждым-форматом">Форматы</a> ·
    <a href="#быстрый-старт">Быстрый старт</a> ·
    <a href="#сравнение">Сравнение</a> ·
    <a href="#плагины">Плагины</a> ·
    <a href="https://www.surfsense.com/pricing">Цены</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | Русский | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

**Отредактируйте договор с отслеживаемыми изменениями и комментариями**

https://github.com/user-attachments/assets/88326b9d-e763-46db-9635-75f9df9e8682

**Добавьте источники из интернета и превратите их в веб-страницу**

https://github.com/user-attachments/assets/073577b7-f055-4f59-8540-330bd764aeb0

SurfSense — бесплатное настольное приложение с открытым кодом для документов, которые нельзя загрузить наружу. Это ИИ-агент в духе NotebookLM, созданный с упором на приватность: он исследует, преобразует и редактирует ваши документы на вашем компьютере. Индекс остаётся на вашем диске, модель, локальную или удалённую, выбираете вы, а аккаунта нет вовсе.

| Платформа | Скачать |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://www.surfsense.com/downloads/windows?src=readme) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://www.surfsense.com/downloads/mac?src=readme) |
| **Linux** x64 | [AppImage](https://www.surfsense.com/downloads/linux-appimage?src=readme) · [deb](https://www.surfsense.com/downloads/linux-deb?src=readme) |

## Быстрый старт

1. Установите SurfSense и пройдите первоначальную настройку.
2. Перетащите свои файлы или папки в источники.
3. Попросите агента искать по вашим файлам, извлекать из них нужное или редактировать их.

## Что SurfSense делает с каждым форматом

| Формат | Исследование (ответы со ссылками) | Создание | Редактирование (в копии) | Преобразование |
|---|---|---|---|---|
| **PDF** | ✓ включая отсканированные страницы³ | ✓ | Заполнение форм и сведение их в плоский вид; нанесение водяных знаков, номеров страниц, верхних и нижних колонтитулов | Объединение, разделение, извлечение, поворот и перестановка страниц |
| **Word** `.docx` | ✓ | ✓ или на основе вашего `.docx` как шаблона | ✓ основной текст, в виде отслеживаемых изменений и комментариев | В PDF¹ |
| **Excel** `.xlsx` | ✓ агент читает и формулы | ✓ с формулами и нативными диаграммами | ✓ значения ячеек и формулы | Анализ в pandas, диаграммы по результатам |
| **PowerPoint** `.pptx` | ✓ | ✓ или на основе вашего `.pptx` как шаблона | Замена текста на слайдах и в заметках; удаление и дублирование слайдов | В PDF¹ |
| **CSV** | ✓ | — | — | Анализ в pandas, диаграммы по результатам |
| **Изображения** PNG, JPEG, TIFF, BMP, WebP | ✓ текст распознаётся через OCR³ | Изображения и инфографика² | — | Вставка в новые документы |
| **Markdown**, обычный текст | ✓ | ✓ Markdown | — | — |
| **HTML** | ✓ | ✓ веб-страница | — | — |
| **Аудиозаписи** WAV, MP3, FLAC, Ogg Vorbis | ✓ расшифровываются на вашем компьютере | — | — | — |
| **Подкаст** (аудио) | — | ✓ с расшифровкой, по умолчанию озвучивается на вашем компьютере | — | — |
| **Интеллект-карты, карточки, тесты** | — | ✓ в приложении | — | — |

<sub>¹ Нужна «Поддержка Office» (LibreOffice), которая включается в «Настройках»; в установщик она не входит никогда. ² Нужна модель для изображений, локальная или удалённая; по умолчанию ни одна не выбрана. ³ OCR распознаёт латиницу, китайскую и японскую письменность.</sub>

Правки, преобразования и инструменты для PDF всегда создают новый файл; оригинал никогда не меняется. Шире всего сейчас поддерживаются PDF, Word и Excel, а поддержка остальных форматов постоянно улучшается.


## Плагины

Подключите их в разделе **Настройки › Плагины**.

**От SurfSense.** Они читают общедоступные страницы без ваших собственных аккаунтов, и для них нужна лицензия SurfSense: [скачайте приложение](https://www.surfsense.com/downloads) и введите в нём свою почту, чтобы получить бесплатную лицензию на 14 дней.

| Плагин | Что делает |
|---|---|
| **Google Search** | Ищет в Google и читает результаты, рекламу и похожие вопросы |
| **Web Crawl** | Читает веб-страницу или обходит весь сайт, превращая его в чистый текст |
| **YouTube** | Читает видео и каналы YouTube, а также комментарии к ним |
| **TikTok** | Читает видео TikTok и комментарии к ним, ищет пользователей и показывает, что сейчас в тренде |
| **Reddit** | Читает публичные посты Reddit с ветками комментариев или целое сообщество |
| **Instagram** | Читает публичные профили, посты и рилсы Instagram и ищет профили |
| **Google Maps** | Находит места на Google Maps и читает отзывы о них |
| **Amazon** | Читает карточки товаров и результаты поиска на Amazon |
| **Walmart** | Читает карточки товаров, результаты поиска и отзывы на Walmart |
| **Indeed** | Читает вакансии на Indeed |

**Сторонние.** MCP-серверы из [реестра плагинов](backend/plugins/registry), например DeepWiki и Notion, или любые другие, которые вы добавите по URL. Лицензия не нужна; они остаются выключенными, пока вы их не разрешите.

## Сравнение

| | NotebookLM (теперь Gemini Notebook) | SurfSense |
|---|---|---|
| Работает без сети / изолирован от сети | Нет | **Да** |
| Документы покидают ваш компьютер | Да | **Нет**, если не выбрать удалённую модель |
| Может редактировать ваши файлы | Нет | **Да** |
| Открытый код | Нет | **Apache-2.0** |
| Модели | Только Gemini | Любой API, совместимый с OpenAI, или локальная модель |

## Сообщество

- [Discord](https://discord.gg/ejRNvftDp9) — для помощи, [Issues](https://github.com/MODSetter/SurfSense/issues) — для ошибок, [Discussions](https://github.com/MODSetter/SurfSense/discussions) — для идей.
- **Участие в разработке:** запросы на слияние направляйте в ветку `dev`; цикл разработки описан в [CONTRIBUTING.md](CONTRIBUTING.md) и [`surfsense_local/`](./surfsense_local). Как всё устроено, рассказано в [`docs/`](docs/README.md).

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors"><img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="Участники SurfSense" /></a>

## Лицензия

Apache-2.0. См. [LICENSE](LICENSE).
