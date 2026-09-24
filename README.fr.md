<!--
  L'encadré de fermeture est daté. Supprimez-le le 18 octobre 2026, à la fin
  de la fenêtre d'export, ainsi que le lien « Importer depuis l'application
  hébergée » plus bas. Ce fichier suit README.md section par section.
  Justification de cette page : plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Forks](https://img.shields.io/github/forks/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/network/members)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img width="128" height="128" alt="SurfSense, l'alternative open source à NotebookLM, isolée du réseau" src="surfsense_web/public/homepage/icon.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>L'alternative open source à NotebookLM, isolée du réseau.</b>
    <br />
    Transformez les documents que vous ne pouvez pas téléverser en synthèses, présentations, rapports, guides d'étude et podcasts, entièrement sur votre propre machine.
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>Télécharger</b></a> ·
    <a href="https://www.surfsense.com/docs">Documentation</a> ·
    <a href="#ce-que-produit-surfsense">Ce qu'il produit</a> ·
    <a href="#comment-surfsense-se-compare">Comparaison</a> ·
    <a href="https://www.surfsense.com/pricing">Tarifs</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | Français | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

<p align="center">
  <img src="surfsense_web/public/homepage/offline-studio.png" alt="L'application de bureau SurfSense avec Studio ouvert et Qwen sélectionné, qui transforme des sources locales en livrables" />
</p>

SurfSense est une application de bureau gratuite et open source pour les documents que vous avez déjà. Déposez-les, posez des questions et obtenez des réponses qui citent leur source, puis transformez les mêmes documents en synthèse, présentation, rapport, guide d'étude ou podcast. Tout tourne sur votre propre machine : l'index est sur votre disque, vous choisissez le modèle, et l'application ne téléverse rien. Il n'y a pas de compte à créer.

**Pour commencer.** Téléchargez l'installateur pour votre machine, puis apportez votre propre clé de modèle ou laissez l'application récupérer un modèle local pour vous.

| Plateforme | Téléchargement |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-Setup.exe) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-arm64.dmg) |
| **Linux** x64 (AppImage) | [SurfSense.AppImage](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.AppImage) |
| **Linux** x64 (deb) | [SurfSense.deb](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.deb) |

Chaque lien pointe en permanence vers la dernière version. Vous pouvez aussi choisir sur [surfsense.com/downloads](https://www.surfsense.com/downloads) ou parcourir [toutes les versions](https://github.com/MODSetter/SurfSense/releases). L'AppImage se met à jour tout seul ; le deb, non.

> [!NOTE]
> **Vous utilisiez l'application web hébergée ?** Elle va être retirée. Ouvrez-la une fois pour exporter vos espaces de travail, puis importez le paquet dans l'application de bureau : documents, dossiers, titres et fils de discussion suivent. La fenêtre d'export se ferme le 18 octobre 2026. Détails sur [la page de fermeture](https://www.surfsense.com/sunset).

## Ce que produit SurfSense

Choisissez quelques documents et un format. L'application le rédige à partir des sources que vous avez choisies, sur votre machine.

| Format | Ce que vous obtenez | Il faut |
|---|---|---|
| **Synthèse** | Un brief structuré des sources sélectionnées | modèle de génération |
| **Cartes mémoire** | Un paquet interactif, une carte à la fois | modèle de génération |
| **Quiz** | Des questions à choix multiples avec les réponses | modèle de génération |
| **Carte mentale** | Une Markmap zoomable, aux nœuds repliables | modèle de génération |
| **Diapositives** | Un `.pptx` modifiable, pas une image de présentation | modèle de génération |
| **Document** | Un rapport `.docx` modifiable | modèle de génération |
| **Tableur** | Un `.xlsx` des tableaux extraits des sources | modèle de génération |
| **Page web** | Une page HTML autonome | modèle de génération |
| **PDF** | Un PDF mis en page | modèle de génération |
| **Podcast** | Une conversation audio à deux voix, lue hors ligne par Kokoro-82M | modèle de génération + modèle audio |
| **Image** | Une illustration pour le contenu | modèle d'image + modèle de génération |
| **Infographie** | Un résumé visuel sur un seul panneau | modèle d'image + modèle de génération |

Certains travaux en demandent plusieurs. Un guide d'étude, c'est une synthèse, un paquet de cartes et un quiz sur le même ensemble de sources, et un brief client est en général la présentation que vous projetez plus la synthèse que vous envoyez ensuite. Les aperçus vidéo ne sont pas encore là.

## Tout reste sur votre machine

On s'en sert pour des dossiers d'affaires, des documents de travail clients, des transcriptions d'entretiens, des spécifications internes, de la recherche non publiée et les notes d'un semestre entier. Vous pouvez interroger l'ensemble, et chaque réponse cite la source dont elle vient. L'application n'en téléverse rien.

- **L'index est local.** L'analyse, le découpage et les embeddings se font sur votre ordinateur, dans SQLite sous `~/.surfsense`. SurfSense n'en garde aucune copie et aucun journal de ce que vous avez demandé.
- **Chaque rôle peut tourner en local.** L'analyseur de documents, le modèle de recherche et la voix du podcast sont dans l'installateur. Le chat et la génération d'images arrivent comme des serveurs locaux dont vous téléchargez les poids une fois, donc vous produisez du texte, de l'audio et des images sans compte ni clé d'API. Nous le vérifions en ingérant un PDF avec le réseau coupé.
- **Les connexions sortantes sont coupées par défaut.** Un panneau de sorties liste chaque destination que l'application peut joindre, et vous activez celles que vous voulez.
- **Pas de télémétrie, pas de rapports de plantage.** Rien ne rappelle la maison, donc il n'y a pas d'option de refus à chercher.

SurfSense ne peut pas vous dire si cela satisfait une réglementation particulière. Cela dépend de vos propres contrôles et de votre régulateur. L'application peut seulement vous dire sur quelle machine se trouvent vos documents.

## Comment SurfSense se compare

Trois sortes de produits sont appelées « le NotebookLM local », et elles répondent à des questions différentes. Aucun n'est un mauvais outil. Ils vous laissent simplement avec des choses différentes.

**Face à Jan, AnythingLLM, Open WebUI, LM Studio.** Ils font tourner un modèle en local et vous donnent un endroit pour lui parler. SurfSense répond à la question suivante : comment en sortir un document fini ? Vous pouvez les combiner en pointant SurfSense vers n'importe quel endpoint compatible OpenAI, y compris l'un des leurs.

**Face à RemNote, Quizlet, NoteGPT, StudyFetch, Gamma.** Eux produisent bien des livrables, et certains sont plus beaux que les nôtres. Le compromis est l'endroit où va votre matériel : vous le téléversez, vous payez chaque mois, et vos fichiers vivent dans le compte de quelqu'un d'autre.

**Face à Google NotebookLM.** Il propose déjà cartes mémoire, quiz, cartes mentales et aperçus audio, donc les deux produisent à peu près les mêmes choses. La différence est la machine qui fait le travail, et le modèle que vous pouvez lui donner.

| | Google NotebookLM | SurfSense |
|---|---|---|
| Fonctionne hors ligne / isolé du réseau | Non | **Oui** |
| Vos documents quittent votre machine | Oui | **Non** |
| Compte requis | Compte Google | **Aucun** |
| Open source | Non | **Apache-2.0** |
| Prix | Offre gratuite ; Pro 19,99 $/mois ; Ultra 249,99 $/mois | **L'application est gratuite** |
| Modèles | Gemini seulement | Toute API compatible OpenAI, ou un modèle local |
| Limites de sources | 50 à 600 sources, 500 000 mots chacune | Ce que votre disque peut contenir |
| Aperçus audio et vidéo | Oui, et meilleurs | Audio oui, hors ligne ; vidéo pas encore |

NotebookLM gagne sur la qualité audio, et il a la vidéo. Si vos sources sur les serveurs de Google vous conviennent, utilisez-le. Sinon, voici le même genre d'outil, sans le téléversement.

## Démarrage rapide

Vous n'avez pas besoin de Docker, d'un terminal, d'un GPU ni d'un fichier compose.

1. **Téléchargez l'installateur** dans le tableau ci-dessus. Il est signé, votre système ne vous opposera donc pas de résistance.
2. **Choisissez un modèle.** Laissez l'application en récupérer un local (Qwen3 en six tailles, à partir de 0,5 GB) ou collez l'URL de base et la clé de n'importe quelle API compatible OpenAI. Le sélecteur vérifie que votre machine peut faire tourner un modèle avant de le proposer, et toute clé que vous lui donnez est stockée chiffrée, le secret dans le trousseau de votre système.
3. **Déposez des documents.** L'application analyse les PDF, les fichiers Office et les images sur votre machine.
4. **Posez des questions.** Chaque réponse cite la source dont elle vient.
5. **Ouvrez Studio,** choisissez un format, récupérez le fichier.

Le téléchargement est la partie lente, parce que l'installateur embarque l'analyseur, le modèle de recherche, la voix du podcast et les serveurs de modèles locaux, pour que l'application fonctionne réseau coupé.

## Documentation et communauté

L'application et ses mises à jour sont gratuites. Une licence ajoute des plugins et un support prioritaire, et ne verrouille rien d'autre : une licence expirée vous laisse l'application et chaque mise à jour future. Voir les [tarifs](https://www.surfsense.com/pricing).

La pile Docker de ce dépôt (`surfsense_backend`, `surfsense_web`, fichiers compose) reste open source et installable, et elle est **soutenue par la communauté : pas de SLA et aucun service hébergé derrière.** L'application de bureau est le chemin pris en charge pour les nouveaux utilisateurs.

- [Documentation](https://www.surfsense.com/docs) pour l'installation, les modèles, les formats Studio et l'auto-hébergement
- [Importer depuis l'application hébergée](https://www.surfsense.com/sunset)
- [Serveur MCP](./surfsense_mcp) pour l'API de scraping hébergée
- [Discord](https://discord.gg/ejRNvftDp9) pour l'aide et les idées, [Discussions](https://github.com/MODSetter/SurfSense/discussions) pour la direction, [Issues](https://github.com/MODSetter/SurfSense/issues) pour les bugs reproductibles
- **Mettez une étoile au dépôt** si vous voulez suivre la suite

## Contribuer

Les pull requests sont les bienvenues, et [CONTRIBUTING.md](CONTRIBUTING.md) décrit tout le parcours. En bref :

- **Trouvez quelque chose à faire :** un ticket étiqueté [`good first issue`](https://github.com/MODSetter/SurfSense/labels/good%20first%20issue) ou [`help wanted`](https://github.com/MODSetter/SurfSense/labels/help%20wanted), ou une ligne de la liste Known gaps (lacunes connues) à la fin de chaque document dans [`docs/architecture/`](docs/architecture/overview.md).
- **Lisez d'abord comment cela fonctionne :** [`docs/`](docs/README.md) explique chaque fonctionnalité et pourquoi elle est construite ainsi, et [`docs/ROADMAP.md`](docs/ROADMAP.md) montre ce sur quoi travaillent les mainteneurs.
- **Ouvrez une PR contre `dev`.** Les corrections de bugs et la documentation n'ont pas besoin d'une discussion préalable ; une nouvelle fonctionnalité commence par une courte proposition de conception. L'application de bureau vit dans [`surfsense_local/`](./surfsense_local), et son README décrit la boucle de développement.

Merci à tous nos Surfers :

<p align="center">
  <a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="Contributeurs de SurfSense" />
  </a>
</p>

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
