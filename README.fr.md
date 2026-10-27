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

  <a href="https://www.surfsense.com/"><img alt="SurfSense, l'alternative open source à NotebookLM, isolée du réseau" src="www/public/homepage/banner.png" /></a>

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
    <a href="#plugins">Plugins</a> ·
    <a href="https://www.surfsense.com/pricing">Tarifs</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | Français | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

**Annotez un contrat avec des modifications suivies et des commentaires**

https://github.com/user-attachments/assets/88326b9d-e763-46db-9635-75f9df9e8682

**Ajoutez des sources depuis le web, puis transformez-les en page web**

https://github.com/user-attachments/assets/073577b7-f055-4f59-8540-330bd764aeb0

SurfSense est une application de bureau gratuite et open source pour les documents que vous ne pouvez pas téléverser. Un agent IA dans l'esprit de NotebookLM, axé sur la confidentialité, qui fait des recherches dans vos documents, les transforme et les modifie, sur votre machine. L'index reste sur votre disque, vous choisissez le modèle, local ou distant, et il n'y a pas de compte à créer.

| Plateforme | Téléchargement |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://www.surfsense.com/downloads/windows?src=readme) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://www.surfsense.com/downloads/mac?src=readme) |
| **Linux** x64 | [AppImage](https://www.surfsense.com/downloads/linux-appimage?src=readme) · [deb](https://www.surfsense.com/downloads/linux-deb?src=readme) |

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
| **Enregistrements** WAV, MP3, FLAC, Ogg Vorbis | ✓ transcrits sur votre machine | — | — | — |
| **Podcast** (audio) | — | ✓ avec transcription, mis en voix sur votre machine par défaut | — | — |
| **Cartes mentales, cartes mémoire, quiz** | — | ✓ dans l'application | — | — |

<sub>¹ Avec la prise en charge d'Office (LibreOffice), que vous activez dans les Paramètres ; LibreOffice n'est jamais inclus dans l'installateur. ² Nécessite un modèle d'image, local ou distant ; aucun n'est choisi par défaut. ³ L'OCR lit les écritures latine, chinoise et japonaise.</sub>

Les modifications, les conversions et les outils PDF créent toujours un nouveau fichier ; votre original n'est jamais modifié. C'est avec les formats PDF, Word et Excel que SurfSense en fait le plus aujourd'hui, et la prise en charge des autres formats continue de s'améliorer.

## Plugins

Connectez-les dans **Paramètres › Plugins**.

**Par SurfSense.** Ils lisent des pages publiques sans passer par vos propres comptes et nécessitent une licence SurfSense : [téléchargez l'application](https://www.surfsense.com/downloads) et saisissez-y votre adresse e-mail pour recevoir une licence gratuite de 14 jours.

| Plugin | Ce qu'il fait |
|---|---|
| **Google Search** | Rechercher sur Google et lire ses résultats, ses annonces et les questions associées |
| **Web Crawl** | Lire une page web, ou explorer un site entier et le convertir en texte propre |
| **YouTube** | Lire le contenu des vidéos et des chaînes YouTube, avec leurs commentaires |
| **TikTok** | Lire le contenu des vidéos TikTok et leurs commentaires, rechercher des utilisateurs et voir ce qui est tendance |
| **Reddit** | Lire les publications publiques de Reddit avec leurs fils de commentaires, ou toute une communauté |
| **Instagram** | Lire les profils, publications et reels publics d'Instagram, et rechercher des profils |
| **Google Maps** | Trouver des lieux sur Google Maps et lire leurs avis |
| **Amazon** | Lire les produits et les résultats de recherche d'Amazon |
| **Walmart** | Lire les produits, les résultats de recherche et les avis de Walmart |
| **Indeed** | Lire les offres d'emploi sur Indeed |

**Tiers.** Des serveurs MCP issus du [registre de plugins](backend/plugins/registry), comme DeepWiki et Notion, ou tout serveur que vous ajoutez par URL. Aucune licence n'est nécessaire ; ils restent désactivés tant que vous ne les autorisez pas.

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

## Licence

Apache-2.0. Voir [LICENSE](LICENSE).
