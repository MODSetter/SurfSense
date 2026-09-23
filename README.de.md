<!--
  Der Abschaltungshinweis ist befristet. Lösche ihn am 18. Oktober 2026, wenn
  das Exportfenster schließt, zusammen mit dem Link „Import aus der gehosteten
  App“ weiter unten. Diese Datei folgt README.md Abschnitt für Abschnitt.
  Begründung dieser Seite: plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Forks](https://img.shields.io/github/forks/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/network/members)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img width="128" height="128" alt="SurfSense, die netzgetrennte Open-Source-Alternative zu NotebookLM" src="surfsense_web/public/homepage/icon.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>Die netzgetrennte Open-Source-Alternative zu NotebookLM.</b>
    <br />
    Mach aus Dokumenten, die du nicht hochladen kannst, Briefings, Folien, Berichte, Lernleitfäden und Podcasts, vollständig auf deinem eigenen Rechner.
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>Download</b></a> ·
    <a href="https://www.surfsense.com/docs">Dokumentation</a> ·
    <a href="#was-surfsense-erstellt">Was es erstellt</a> ·
    <a href="#so-vergleicht-sich-surfsense">Vergleich</a> ·
    <a href="https://www.surfsense.com/pricing">Preise</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | Deutsch | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

<p align="center">
  <img src="surfsense_web/public/homepage/offline-studio.png" alt="Die SurfSense-Desktop-App mit geöffnetem Studio und ausgewähltem Qwen, die lokale Quellen in Ergebnisse verwandelt" />
</p>

SurfSense ist eine kostenlose Open-Source-Desktop-App für die Dokumente, die du schon hast. Zieh sie hinein, stell Fragen und bekommst Antworten, die ihre Quelle nennen. Dieselben Dokumente werden daraus ein Briefing, eine Folienpräsentation, ein Bericht, ein Lernleitfaden oder ein Podcast. Alles läuft auf deinem eigenen Rechner: Der Index liegt auf deiner Festplatte, du wählst das Modell, und die App lädt nichts hoch. Ein Konto brauchst du nicht.

**Loslegen.** Lade das Installationsprogramm für deinen Rechner herunter. Danach bringst du einen eigenen Modellschlüssel mit oder lässt die App ein lokales Modell für dich holen.

| Plattform | Download |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-Setup.exe) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-arm64.dmg) |
| **Linux** x64 (AppImage) | [SurfSense.AppImage](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.AppImage) |
| **Linux** x64 (deb) | [SurfSense.deb](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.deb) |

Jeder Link zeigt dauerhaft auf die neueste Version. Du kannst auch auf [surfsense.com/downloads](https://www.surfsense.com/downloads) wählen oder [alle Versionen](https://github.com/MODSetter/SurfSense/releases) durchsehen. Das AppImage aktualisiert sich selbst, das deb nicht.

> [!NOTE]
> **Die gehostete Web-App genutzt?** Sie wird eingestellt. Öffne sie einmal, exportiere deine Arbeitsbereiche und importiere das Paket in die Desktop-App. Dokumente, Ordner, Titel und Chatverläufe kommen mit. Das Exportfenster schließt am 18. Oktober 2026. Details auf [der Abschaltungsseite](https://www.surfsense.com/sunset).

## Was SurfSense erstellt

Wähl ein paar Dokumente und ein Format. Die App schreibt das Ergebnis aus den Quellen, die du ausgewählt hast, auf deinem Rechner.

| Format | Was du bekommst | Braucht |
|---|---|---|
| **Zusammenfassung** | Ein strukturiertes Briefing der ausgewählten Quellen | Generierungsmodell |
| **Karteikarten** | Ein interaktives Deck, eine Karte nach der anderen | Generierungsmodell |
| **Quiz** | Multiple-Choice-Fragen mit Antworten | Generierungsmodell |
| **Mindmap** | Eine Markmap zum Zoomen und Einklappen | Generierungsmodell |
| **Folien** | Eine bearbeitbare `.pptx`, kein Bild einer Präsentation | Generierungsmodell |
| **Dokument** | Ein bearbeitbarer `.docx`-Bericht | Generierungsmodell |
| **Tabellenkalkulation** | Eine `.xlsx` mit den Tabellen aus den Quellen | Generierungsmodell |
| **Webseite** | Eine eigenständige HTML-Seite | Generierungsmodell |
| **PDF** | Ein gesetztes PDF | Generierungsmodell |
| **Podcast** | Ein Zwiegespräch als Audio, offline gesprochen von Kokoro-82M | Generierungsmodell + mitgelieferte Stimme |
| **Bild** | Eine Illustration zum Material | Bildmodell + Generierungsmodell |
| **Infografik** | Eine visuelle Zusammenfassung auf einem Panel | Bildmodell + Generierungsmodell |

Manche Aufträge brauchen mehr als ein Format. Ein Lernleitfaden ist Zusammenfassung, Karteikarten und Quiz über denselben Quellensatz, und ein Kunden-Briefing ist meist die Präsentation, aus der du vorträgst, plus die Zusammenfassung, die du danach schickst. Video-Überblicke gibt es noch nicht.

## Alles bleibt auf deinem Rechner

Leute richten das auf Fallakten, Arbeitsunterlagen von Mandanten, Interview-Transkripte, interne Spezifikationen, unveröffentlichte Forschung und die Mitschriften eines ganzen Semesters. Du kannst über all das Fragen stellen, und jede Antwort nennt die Quelle, aus der sie kommt. Die App lädt davon nichts hoch.

- **Der Index ist lokal.** Parsen, Zerteilen und Embeddings laufen auf deinem Computer, in SQLite unter `~/.surfsense`. SurfSense behält keine Kopie und kein Protokoll dessen, was du gefragt hast.
- **Jede Rolle kann lokal laufen.** Der Dokumenten-Parser, das Retrieval-Modell und die Podcast-Stimme stecken im Installationsprogramm. Chat und Bilderzeugung kommen als lokale Server, deren Gewichte du einmal herunterlädst. Text, Audio und Bilder gehen also ohne Konto und ohne API-Schlüssel. Wir prüfen das, indem wir ein PDF bei abgeschaltetem Netzwerk einlesen.
- **Ausgehende Verbindungen sind standardmäßig aus.** Ein Ausgangspanel listet jedes Ziel, das die App erreichen kann, und du schaltest die frei, die du willst.
- **Keine Telemetrie, keine Absturzberichte.** Nichts meldet sich nach Hause, also gibt es auch keinen Schalter, den du erst suchen müsstest.

SurfSense kann dir nicht sagen, ob das eine bestimmte Vorschrift erfüllt. Das hängt von deinen eigenen Kontrollen und deiner Aufsicht ab. Die App kann dir nur sagen, auf welchem Rechner deine Dokumente liegen.

## So vergleicht sich SurfSense

Drei Arten von Produkten heißen „das lokale NotebookLM“, und sie beantworten verschiedene Fragen. Keines davon ist ein schlechtes Werkzeug. Du behältst am Ende nur unterschiedliche Dinge.

**Gegenüber Jan, AnythingLLM, Open WebUI, LM Studio.** Die führen ein Modell lokal aus und geben dir einen Ort, an dem du damit reden kannst. SurfSense beantwortet die nächste Frage: Wie kommt ein fertiges Dokument dabei heraus? Du kannst sie zusammen nutzen, indem du SurfSense auf einen beliebigen OpenAI-kompatiblen Endpunkt richtest, auch auf einen von ihnen.

**Gegenüber RemNote, Quizlet, NoteGPT, StudyFetch, Gamma.** Die erzeugen Ergebnisse, und manche sehen besser aus als unsere. Der Preis ist, wohin dein Material geht: Du lädst es hoch, zahlst monatlich, und deine Dateien liegen im Konto von jemand anderem.

**Gegenüber Google NotebookLM.** Es liefert schon Karteikarten, Quizze, Mindmaps und Audio-Überblicke, also entsteht auf beiden Seiten weitgehend dasselbe. Der Unterschied ist, wessen Rechner die Arbeit macht und welches Modell du darauf richten kannst.

| | Google NotebookLM | SurfSense |
|---|---|---|
| Läuft offline / netzgetrennt | Nein | **Ja** |
| Deine Dokumente verlassen deinen Rechner | Ja | **Nein** |
| Konto nötig | Google-Konto | **Keins** |
| Open Source | Nein | **Apache-2.0** |
| Preis | Kostenlose Stufe; Pro 19,99 $/Monat; Ultra 249,99 $/Monat | **Die App ist kostenlos** |
| Modelle | Nur Gemini | Jede OpenAI-kompatible API, oder ein lokales Modell |
| Quellenlimits | 50 bis 600 Quellen, je 500.000 Wörter | Was auf deine Festplatte passt |
| Audio- und Video-Überblicke | Ja, und besser | Audio ja, offline; Video noch nicht |

NotebookLM gewinnt bei der Audioqualität und hat Video. Wenn dir reicht, dass deine Quellen auf Googles Servern liegen, nimm es. Wenn nicht, ist das hier dieselbe Art Werkzeug, ohne den Upload.

## Schnellstart

Du brauchst kein Docker, kein Terminal, keine GPU und keine Compose-Datei.

1. **Lade das Installationsprogramm** aus der Tabelle oben. Es ist signiert, dein Betriebssystem stellt sich also nicht quer.
2. **Wähl ein Modell.** Lass die App ein lokales holen (Qwen3 in sechs Größen, ab 0,5 GB) oder füge Basis-URL und Schlüssel einer beliebigen OpenAI-kompatiblen API ein. Die Auswahl prüft, ob dein Rechner ein Modell ausführen kann, bevor sie es anbietet. Jeder Schlüssel, den du angibst, wird verschlüsselt gespeichert, das Geheimnis liegt im Schlüsselbund deines Betriebssystems.
3. **Wirf Dokumente hinein.** Die App liest PDFs, Office-Dateien und Bilder auf deinem Rechner.
4. **Stell Fragen.** Jede Antwort nennt die Quelle, aus der sie kommt.
5. **Öffne Studio,** wähl ein Format, nimm die Datei mit.

Der Download ist der langsame Teil, weil das Installationsprogramm Parser, Retrieval-Modell, Podcast-Stimme und die lokalen Modellserver mitbringt. Die App funktioniert deshalb auch ohne Netz.

## Dokumentation und Community

Die App und ihre Updates sind kostenlos. Eine Lizenz fügt Plugins und bevorzugten Support hinzu und sperrt sonst nichts. Eine abgelaufene Lizenz lässt dir die App und jedes künftige Update. Siehe [Preise](https://www.surfsense.com/pricing).

Der Docker-Stack in diesem Repo (`surfsense_backend`, `surfsense_web`, Compose-Dateien) bleibt Open Source und installierbar und wird **von der Community getragen: kein SLA und kein gehosteter Dienst dahinter.** Die Desktop-App ist der unterstützte Weg für neue Nutzer.

- [Dokumentation](https://www.surfsense.com/docs) zu Installation, Modellen, Studio-Formaten und Self-Hosting
- [Import aus der gehosteten App](https://www.surfsense.com/sunset)
- [MCP-Server](./surfsense_mcp) für die gehostete Scraper-API
- [Discord](https://discord.gg/ejRNvftDp9) für Hilfe und Ideen, [Discussions](https://github.com/MODSetter/SurfSense/discussions) für die Richtung, [Issues](https://github.com/MODSetter/SurfSense/issues) für nachvollziehbare Fehler
- **Gib dem Repo einen Stern,** wenn du verfolgen willst, wohin das geht

## Mitwirken

Pull Requests sind willkommen, und [CONTRIBUTING.md](CONTRIBUTING.md) geht den ganzen Ablauf durch. Kurz gesagt:

- **Such dir etwas zum Bearbeiten:** ein Issue mit dem Label [`good first issue`](https://github.com/MODSetter/SurfSense/labels/good%20first%20issue) oder [`help wanted`](https://github.com/MODSetter/SurfSense/labels/help%20wanted), oder eine Zeile aus der Liste Known gaps (bekannte Lücken) am Ende jedes Dokuments in [`docs/architecture/`](docs/architecture/overview.md).
- **Lies zuerst, wie es funktioniert:** [`docs/`](docs/README.md) erklärt jedes Feature und warum es so gebaut ist, und [`docs/ROADMAP.md`](docs/ROADMAP.md) zeigt, woran die Maintainer arbeiten.
- **Öffne einen PR gegen `dev`.** Fehlerbehebungen und Doku brauchen vorher keine Diskussion. Ein neues Feature beginnt mit einem kurzen Designvorschlag. Die Desktop-App liegt in [`surfsense_local/`](./surfsense_local), und deren README beschreibt die Entwicklungsschleife.

Danke an alle unsere Surfers:

<p align="center">
  <a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="SurfSense-Mitwirkende" />
  </a>
</p>

## Sterneverlauf

<p align="center">
  <a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
    </picture>
  </a>
</p>

## Lizenz

Apache-2.0. Siehe [LICENSE](LICENSE).
