<!--
  L'encadré de fermeture est temporaire : supprimez-le le 18 octobre 2026, en même
  temps que l'encadré correspondant de README.md. Ce fichier suit README.md section par section.
  Justification : plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img alt="SurfSense, l'alternative open source à NotebookLM, isolée du réseau" src="surfsense_web/public/homepage/banner.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>L'alternative open source à NotebookLM, isolée du réseau.</b>
    <br />
    L'agent IA qui fait des recherches dans vos documents, les transforme et les modifie, sur votre machine.
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>Télécharger</b></a> ·
    <a href="#ce-que-surfsense-fait-avec-chaque-format">Formats</a> ·
    <a href="#démarrage-rapide">Démarrage rapide</a> ·
    <a href="#comparaison">Comparaison</a> ·
    <a href="https://www.surfsense.com/pricing">Tarifs</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | Français | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

https://github.com/user-attachments/assets/88326b9d-e763-46db-9635-75f9df9e8682

SurfSense est une application de bureau gratuite et open source pour les documents que vous ne pouvez pas téléverser. Un agent IA dans l'esprit de NotebookLM, axé sur la confidentialité, qui fait des recherches dans vos documents, les transforme et les modifie, sur votre machine. L'index reste sur votre disque, vous choisissez le modèle, local ou distant, et il n'y a pas de compte à créer.

| Plateforme | Téléchargement |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-Setup.exe) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-arm64.dmg) |
| **Linux** x64 | [AppImage](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.AppImage) · [deb](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.deb) |

> [!NOTE]
> **Vous utilisiez l'application web hébergée ?** Exportez vos espaces de travail avant le 18 octobre 2026 et importez-les ici. Voir [la page de fermeture](https://www.surfsense.com/sunset).

## Démarrage rapide

1. Installez SurfSense et effectuez la configuration initiale.
2. Déposez vos fichiers ou dossiers dans vos sources.
3. Demandez à l'agent de faire des recherches dans vos fichiers, d'en extraire du contenu ou de les modifier.

## Ce que SurfSense fait avec chaque format

| Format | Rechercher (réponses sourcées) | Créer | Modifier (sur une copie) | Transformer |
|---|---|---|---|---|
| **PDF** | ✓ pages numérisées comprises³ | ✓ | Remplir et aplatir des formulaires ; apposer des filigranes, des numéros de page, des en-têtes et des pieds de page | Fusionner, diviser, extraire, faire pivoter, réordonner des pages |
| **Word** `.docx` | ✓ | ✓ ou à partir de votre propre `.docx` comme modèle | ✓ corps du texte, sous forme de modifications suivies et de commentaires | En PDF¹ |
| **Excel** `.xlsx` | ✓ l'agent lit aussi les formules | ✓ avec formules et graphiques natifs | ✓ valeurs des cellules et formules | Analyser avec pandas, mettre les résultats en graphique |
| **PowerPoint** `.pptx` | ✓ | ✓ ou à partir de votre propre `.pptx` comme modèle | Remplacer le texte des diapositives et des notes ; supprimer ou dupliquer des diapositives | En PDF¹ |
| **CSV** | ✓ | — | — | Analyser avec pandas, mettre les résultats en graphique |
| **Images** PNG, JPEG, TIFF, BMP, WebP | ✓ texte lu par OCR³ | Images et infographies² | — | Insérer dans de nouveaux documents |
| **Markdown**, texte brut | ✓ | ✓ Markdown | — | — |
| **HTML** | ✓ | ✓ page web | — | — |
| **Podcast** (audio) | — | ✓ avec transcription, mis en voix sur votre machine par défaut | — | — |
| **Cartes mentales, cartes mémoire, quiz** | — | ✓ dans l'application | — | — |

<sub>¹ Avec la prise en charge d'Office (LibreOffice), que vous activez dans les Paramètres ; LibreOffice n'est jamais inclus dans l'installateur. ² Nécessite un modèle d'image, local ou distant ; aucun n'est choisi par défaut. ³ L'OCR lit les écritures latine, chinoise et japonaise.</sub>

Les modifications, les conversions et les outils PDF créent toujours un nouveau fichier ; votre original n'est jamais modifié. C'est avec les formats PDF, Word et Excel que SurfSense en fait le plus aujourd'hui, et la prise en charge des autres formats continue de s'améliorer.

## Comparaison

| | NotebookLM (désormais Gemini Notebook) | SurfSense |
|---|---|---|
| Fonctionne hors ligne / isolé du réseau | Non | **Oui** |
| Vos documents quittent votre machine | Oui | **Non**, sauf si vous choisissez un modèle distant |
| Peut modifier vos fichiers | Non | **Oui** |
| Open source | Non | **Apache-2.0** |
| Modèles | Gemini seulement | Toute API compatible OpenAI, ou un modèle local |

## Communauté

- [Discord](https://discord.gg/ejRNvftDp9) pour l'aide, [Issues](https://github.com/MODSetter/SurfSense/issues) pour les bugs, [Discussions](https://github.com/MODSetter/SurfSense/discussions) pour les idées.
- **Contribuer :** les PR ciblent `dev` ; voir [CONTRIBUTING.md](CONTRIBUTING.md) et [`surfsense_local/`](./surfsense_local) pour la boucle de développement. Le fonctionnement de SurfSense est expliqué dans [`docs/`](docs/README.md).

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors"><img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="Contributeurs de SurfSense" /></a>

## Historique des étoiles

<p align="center">
  <a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
    </picture>
  </a>
</p>

## Licence

Apache-2.0. Voir [LICENSE](LICENSE).
