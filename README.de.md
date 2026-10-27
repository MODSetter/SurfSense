<!--
  Der Abschaltungshinweis ist befristet: Lösche ihn am 18. Oktober 2026, zusammen
  mit dem entsprechenden Hinweis in README.md. Diese Datei folgt README.md Abschnitt für Abschnitt.
  Begründung: plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img alt="SurfSense, die netzgetrennte Open-Source-Alternative zu NotebookLM" src="www/public/homepage/banner.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>Die netzgetrennte Open-Source-Alternative zu NotebookLM.</b>
    <br />
    Der KI-Agent, der in deinen Dokumenten recherchiert, sie umwandelt und bearbeitet – auf deinem Rechner.
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>Download</b></a> ·
    <a href="#was-surfsense-mit-jedem-format-macht">Formate</a> ·
    <a href="#schnellstart">Schnellstart</a> ·
    <a href="#surfsense-im-vergleich">Vergleich</a> ·
    <a href="#plugins">Plugins</a> ·
    <a href="https://www.surfsense.com/pricing">Preise</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | Deutsch | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

**Einen Vertrag mit nachverfolgten Änderungen und Kommentaren redigieren**

https://github.com/user-attachments/assets/88326b9d-e763-46db-9635-75f9df9e8682

**Quellen aus dem Web hinzufügen und daraus eine Webseite machen**

https://github.com/user-attachments/assets/073577b7-f055-4f59-8540-330bd764aeb0

SurfSense ist eine kostenlose Open-Source-Desktop-App für Dokumente, die du nicht hochladen kannst. Ein auf Datenschutz ausgelegter KI-Agent im Stil von NotebookLM, der auf deinem Rechner in deinen Dokumenten recherchiert, sie umwandelt und bearbeitet. Der Index bleibt auf deiner Festplatte, du wählst das Modell, lokal oder remote, und es gibt kein Konto.

| Plattform | Download |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://www.surfsense.com/downloads/windows?src=readme) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://www.surfsense.com/downloads/mac?src=readme) |
| **Linux** x64 | [AppImage](https://www.surfsense.com/downloads/linux-appimage?src=readme) · [deb](https://www.surfsense.com/downloads/linux-deb?src=readme) |

## Schnellstart

1. Installiere SurfSense und durchlaufe beim ersten Start die Einrichtung.
2. Zieh deine Dateien oder Ordner in deine Quellen.
3. Bitte den Agenten, deine Dateien zu durchsuchen, etwas daraus zu extrahieren oder sie zu bearbeiten.

## Was SurfSense mit jedem Format macht

| Format | Recherchieren (Antworten mit Quellenangabe) | Erstellen | Bearbeiten (als Kopie) | Umwandeln |
|---|---|---|---|---|
| **PDF** | ✓ auch gescannte Seiten³ | ✓ | Formulare ausfüllen und abflachen; Wasserzeichen, Seitenzahlen, Kopf- und Fußzeilen einfügen | Zusammenführen, aufteilen, Seiten extrahieren, drehen, neu anordnen |
| **Word** `.docx` | ✓ | ✓ oder aus deiner eigenen `.docx` als Vorlage | ✓ Fließtext, als nachverfolgte Änderungen und Kommentare | In PDF¹ |
| **Excel** `.xlsx` | ✓ der Agent liest auch Formeln | ✓ mit Formeln und nativen Diagrammen | ✓ Zellwerte und Formeln | Mit pandas analysieren, Ergebnisse als Diagramm darstellen |
| **PowerPoint** `.pptx` | ✓ | ✓ oder aus deiner eigenen `.pptx` als Vorlage | Text auf Folien und in Notizen ersetzen; Folien löschen oder duplizieren | In PDF¹ |
| **CSV** | ✓ | — | — | Mit pandas analysieren, Ergebnisse als Diagramm darstellen |
| **Bilder** PNG, JPEG, TIFF, BMP, WebP | ✓ Text per OCR erkannt³ | Bilder und Infografiken² | — | In neue Dokumente einfügen |
| **Markdown**, reiner Text | ✓ | ✓ Markdown | — | — |
| **HTML** | ✓ | ✓ Webseite | — | — |
| **Aufnahmen** WAV, MP3, FLAC, Ogg Vorbis | ✓ auf deinem Rechner transkribiert | — | — | — |
| **Podcast** (Audio) | — | ✓ mit Transkript, standardmäßig auf deinem Rechner vertont | — | — |
| **Mindmaps, Karteikarten, Quizze** | — | ✓ in der App | — | — |

<sub>¹ Mit Office-Unterstützung (LibreOffice), die du in den Einstellungen einschaltest; LibreOffice ist nie im Installationsprogramm enthalten. ² Braucht ein Bildmodell, lokal oder remote; standardmäßig ist keins ausgewählt. ³ Die OCR erkennt lateinische, chinesische und japanische Schrift.</sub>

Bearbeitungen, Umwandlungen und PDF-Werkzeuge erzeugen immer eine neue Datei; dein Original wird nie verändert. Bei PDF, Word und Excel kann SurfSense heute am meisten, und die Unterstützung der anderen Formate wird laufend besser.

## Plugins

Verbinde sie unter **Einstellungen › Plugins**.

**Von SurfSense.** Diese Plugins lesen öffentliche Seiten ohne deine eigenen Konten und brauchen eine SurfSense-Lizenz: [Lade die App herunter](https://www.surfsense.com/downloads) und gib dort deine E-Mail-Adresse ein, dann bekommst du eine kostenlose Lizenz für 14 Tage.

| Plugin | Was es macht |
|---|---|
| **Google Search** | Google durchsuchen und die Ergebnisse, Anzeigen und verwandten Fragen lesen |
| **Web Crawl** | Eine Webseite lesen oder eine ganze Website crawlen und in sauberen Text umwandeln |
| **YouTube** | YouTube-Videos, -Kanäle und ihre Kommentare lesen |
| **TikTok** | TikTok-Videos und ihre Kommentare lesen, Nutzer suchen und sehen, was gerade angesagt ist |
| **Reddit** | Öffentliche Reddit-Beiträge mit ihren Kommentarverläufen oder eine ganze Community lesen |
| **Instagram** | Öffentliche Instagram-Profile, -Beiträge und -Reels lesen und Profile suchen |
| **Google Maps** | Orte auf Google Maps finden und ihre Bewertungen lesen |
| **Amazon** | Amazon-Produkte und Suchergebnisse lesen |
| **Walmart** | Walmart-Produkte, Suchergebnisse und Bewertungen lesen |
| **Indeed** | Stellenanzeigen auf Indeed lesen |

**Drittanbieter.** MCP-Server aus der [Plugin-Registry](backend/plugins/registry), etwa DeepWiki und Notion, oder jeder, den du per URL hinzufügst. Keine Lizenz nötig; sie bleiben aus, bis du sie erlaubst.

## SurfSense im Vergleich

| | NotebookLM (jetzt Gemini Notebook) | SurfSense |
|---|---|---|
| Läuft offline / netzgetrennt | Nein | **Ja** |
| Deine Dokumente verlassen deinen Rechner | Ja | **Nein**, außer du wählst ein Remote-Modell |
| Kann deine Dateien bearbeiten | Nein | **Ja** |
| Open Source | Nein | **Apache-2.0** |
| Modelle | Nur Gemini | Jede OpenAI-kompatible API oder ein lokales Modell |

## Community

- [Discord](https://discord.gg/ejRNvftDp9) für Hilfe, [Issues](https://github.com/MODSetter/SurfSense/issues) für Fehler, [Discussions](https://github.com/MODSetter/SurfSense/discussions) für Ideen.
- **Mitwirken:** PRs werden gegen `dev` geöffnet; siehe [CONTRIBUTING.md](CONTRIBUTING.md) und [`surfsense_local/`](./surfsense_local) für die Entwicklungsschleife. Wie SurfSense funktioniert, steht in [`docs/`](docs/README.md).

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors"><img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="SurfSense-Mitwirkende" /></a>

## Lizenz

Apache-2.0. Siehe [LICENSE](LICENSE).
