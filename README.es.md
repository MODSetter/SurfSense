<a href="https://www.surfsense.com/"><img width="1584" height="396" alt="SurfSense, la plataforma de inteligencia competitiva de código abierto para agentes de IA" src="https://github.com/user-attachments/assets/9361ef58-1753-4b6e-b275-5020d8847261" /></a>



<div align="center">
<a href="https://discord.gg/ejRNvftDp9">
<img src="https://img.shields.io/discord/1359368468260192417" alt="Discord">
</a>
<a href="https://www.reddit.com/r/SurfSense/">
<img src="https://img.shields.io/reddit/subreddit-subscribers/SurfSense?style=social" alt="Reddit">
</a>
</div>

<div align="center">

[English](README.md) | [Español](README.es.md) | [Português](README.pt-BR.md) | [हिन्दी](README.hi.md) | [简体中文](README.zh-CN.md)

</div>
<div align="center">
<a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter%2FSurfSense | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>

# SurfSense: Dale inteligencia competitiva a tus agentes de IA

SurfSense es la **plataforma de inteligencia competitiva de código abierto para agentes de IA**. Tus agentes monitorean a la competencia, siguen los rankings y escuchan a tu mercado con datos en vivo de **Reddit, YouTube, Google Maps, Google Search y la web abierta**, a través de una única **API REST** o un **servidor MCP**. Agentes programados y activados por eventos convierten lo que encuentran en informes y alertas, y una base de conocimiento integrada mantiene cada hallazgo disponible para búsqueda con citas.

> [!NOTE]
> **📢 Una nota para nuestros usuarios de la alternativa a NotebookLM**
>
> Durante los últimos meses construimos SurfSense como el mejor agente de investigación general para tu propio conocimiento, y ese capítulo nos dio una comunidad de la que estamos genuinamente orgullosos. Herramientas agénticas como Claude, OpenCode, Hermes y OpenClaw ya han demostrado que los agentes son el futuro, y la investigación general se está convirtiendo en algo que todo agente capaz hace de fábrica. Lo que a los agentes todavía les falta son **datos de mercado en vivo y los flujos de trabajo a su alrededor**, así que ahí es donde estamos dirigiendo toda nuestra energía: convertirnos en la plataforma definitiva de agentes de inteligencia competitiva de código abierto.
>
> **Nada de lo que dependes va a desaparecer.** Tu base de conocimiento, el chat con citas, los informes, los podcasts, las presentaciones, las automatizaciones y los chats colaborativos siguen funcionando, y el autoalojamiento sigue siendo gratuito y de código abierto. Lee el anuncio completo en [nuestro changelog](https://www.surfsense.com/changelog).

## Por qué los agentes necesitan SurfSense

Pregúntale a cualquier agente capaz "¿cuánto están cobrando los competidores esta semana?" o "¿qué está diciendo Reddit sobre nosotros desde el lanzamiento?" y no tiene ningún lugar confiable donde buscar. Las APIs oficiales de las plataformas tienen límites de tasa, precios pensados para empresas grandes o directamente no existen, y la infraestructura de scraping es frágil. SurfSense cierra esa brecha:

- **Conectores nativos por plataforma**, cada uno un endpoint REST tipado que devuelve JSON estructurado. Sin ruleta de límites de tasa, sin parsear HTML.
- **Un servidor MCP** que expone cada conector como una herramienta nativa (`surfsense_reddit_scrape`, `surfsense_google_search` y más) para Claude, Cursor o cualquier framework de agentes.
- **Un arnés de agentes**, no solo datos en bruto: reintentos, salida estructurada y medición de créditos vienen integrados, así que los agentes pasan de una pregunta a un informe sin que tú construyas la infraestructura.
- **Código abierto y autoalojable**, para que tu investigación competitiva se quede en tu propia infraestructura.

## Conectores de datos en vivo

| Conector | Qué obtienen tus agentes | Más información |
|---|---|---|
| **Reddit** | Publicaciones, comentarios y flujos de subreddits sin los límites de tasa de la API oficial | [Reddit Scraper API](https://www.surfsense.com/reddit) |
| **YouTube** | Videos, transcripciones e hilos de comentarios para escuchar a tu marca y productos | [YouTube Scraper API](https://www.surfsense.com/youtube) |
| **Google Maps** | Lugares, calificaciones y reseñas para investigar competidores locales y prospectos | [Google Maps Scraper API](https://www.surfsense.com/google-maps) |
| **Google Search** | SERPs en vivo para seguimiento de posiciones y monitoreo de mercado | [Google Search API](https://www.surfsense.com/google-search) |
| **Web Crawl** (rastreo web) | Cualquier página de la web abierta como contenido limpio y estructurado | [Web Crawling API](https://www.surfsense.com/web-crawl) |
| **Conectores MCP externos** | Conecta cualquier servidor MCP a tus agentes, con OAuth de un clic para Notion, Slack, Jira y más | [External MCP Connectors](https://www.surfsense.com/external-mcp-connectors) |

La facturación es de pago por uso: los conectores facturan por elemento realmente devuelto, los rastreos por página obtenida con éxito, y las llamadas fallidas nunca se facturan. Las instalaciones autoalojadas funcionan con la facturación desactivada. Consulta los [precios](https://www.surfsense.com/pricing).

## Inicio rápido

### Llama a un conector desde código

Cada conector es un endpoint REST que puedes llamar desde cualquier lenguaje con tu clave de API de SurfSense:

```bash
curl -X POST "$SURFSENSE_API_URL/workspaces/$WORKSPACE_ID/scrapers/reddit/scrape" \
  -H "Authorization: Bearer $SURFSENSE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "search_queries": ["your brand"],
    "community": "webscraping",
    "sort": "top",
    "time_filter": "week"
  }'
```

Cada [página de conector](https://www.surfsense.com/connectors) tiene ejemplos listos para copiar y pegar en Python, JavaScript, Go, PHP, Ruby, Java y C#.

### Dale las herramientas a tus agentes vía MCP

Agrega el servidor MCP de SurfSense a Claude, Cursor o tu propio framework de agentes:

```json
{
  "mcpServers": {
    "surfsense": {
      "url": "https://mcp.surfsense.com",
      "headers": { "Authorization": "Bearer ${SURFSENSE_API_KEY}" }
    }
  }
}
```

Tu agente ahora puede llamar a cada conector como una herramienta nativa. Consulta la página del [servidor MCP de SurfSense](https://www.surfsense.com/mcp-server) para ver la lista completa de herramientas, o ejecuta el servidor localmente desde [`surfsense_mcp`](./surfsense_mcp).

### Usa la nube

Ve a [surfsense.com](https://www.surfsense.com), inicia sesión y pídele al agente datos de mercado en vivo en lenguaje natural. Las cuentas nuevas comienzan con $5 de crédito gratuito y sin suscripción.


### Autoalójalo gratis

Ejecuta toda la plataforma, los conectores, los agentes, las automatizaciones y el servidor MCP en tu propia infraestructura. Las instalaciones autoalojadas vienen con la facturación desactivada, así que el scraping, el rastreo y las ejecuciones de agentes solo están limitados por tu hardware y las claves de modelos que aportes.

**Requisitos previos:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) debe estar instalado y en ejecución.

Para Linux/macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
```

Para Windows:

```bash
irm https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.ps1 | iex
```

El script de instalación configura [Watchtower](https://github.com/nicholas-fedor/watchtower) automáticamente para actualizaciones automáticas diarias. Para omitirlo, agrega la opción `--no-watchtower`. Para Docker Compose, instalación manual y otras opciones de despliegue, consulta la [documentación](https://www.surfsense.com/docs/).

## Flujos de trabajo de inteligencia competitiva

Las automatizaciones ejecutan turnos completos de agente según un horario o en respuesta a eventos, y luego escriben los resultados en Notion, Slack, Linear y Jira. Describe el flujo de trabajo en lenguaje natural y SurfSense lo construye, sin necesidad de código. Prueba con instrucciones como:

- "Vigila las páginas de precios de nuestros 3 principales competidores y avísame en Slack cuando cambie un plan o un precio."
- "Rastrea cada mención de nuestra marca en Reddit y YouTube y envíame un resumen diario."
- "Monitorea nuestro ranking en Google para nuestras 10 palabras clave principales y señala las caídas semana a semana."
- "Extrae las nuevas reseñas de Google Maps de nuestras ubicaciones y las de nuestros competidores cada lunes."
- "Ejecuta un informe mensual de análisis de la competencia y guárdalo en mi espacio de trabajo."


## Todo lo demás que viene incluido

El espacio de trabajo de investigación que convirtió a SurfSense en la alternativa de código abierto líder a NotebookLM sigue aquí, y todo lo que tus agentes recopilan aterriza en él.

**Base de conocimiento**

- Sube PDFs, documentos de Office, imágenes y audio, o sincroniza **Google Drive, OneDrive y Dropbox**. Más de 50 formatos de archivo compatibles.
- Búsqueda híbrida semántica y de texto completo con respuestas citadas al estilo Perplexity.
- La organización de archivos con IA clasifica los documentos automáticamente por fuente, fecha y tema.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="Chatea con tus PDFs y documentos" /></p>

**Estudio de entregables**

- Generador de informes con IA con exportación a PDF, DOCX, HTML, LaTeX, EPUB, ODT o texto plano.
- Podcasts de IA con dos presentadores a partir de cualquier documento o carpeta en menos de 20 segundos.
- Presentaciones de diapositivas editables, resúmenes en video narrados y generación de imágenes con IA.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ReportGenGif_compressed.gif" alt="Generador de informes con IA" /></p>

**Colaboración en equipo**

- Chats de IA colaborativos en tiempo real con comentarios y menciones.
- RBAC con roles de Propietario, Administrador, Editor y Visualizador.

<p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeChatGif.gif" alt="Chat de IA colaborativo" /></p>

**Aplicación de escritorio**

Asistencia de IA nativa en todas las aplicaciones de tu computadora. Descárgala desde la [última versión](https://github.com/MODSetter/SurfSense/releases/latest).

- **General Assist**: abre SurfSense desde cualquier aplicación con un atajo global.
- **Quick Assist**: selecciona texto en cualquier lugar y pídele a la IA que lo explique, lo reescriba o actúe sobre él.
- **Screenshot Assist**: captura cualquier región de tu pantalla y pregúntale a la IA sobre ella.
- **Watch Local Folder** (vigilar carpeta local): sincroniza automáticamente una carpeta local con tu base de conocimiento. Apúntala a tu bóveda de Obsidian para mantener tus notas disponibles para búsqueda.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/quick_assist.gif" alt="Quick Assist" /></p>

**Sin dependencia de un proveedor**

- Más de 100 LLMs vía la especificación de OpenAI y LiteLLM, incluidos GPT-5.5, Claude Sonnet 5 y Gemini 3.1 Pro.
- Más de 6,000 modelos de embeddings y todos los rerankers principales.
- Soporte completo para LLMs locales y privados (vLLM, Ollama), para que tus datos sigan siendo tuyos.

## Muestra del agente de video

https://github.com/user-attachments/assets/012a7ffa-6f76-4f06-9dda-7632b470057a

## Muestra del agente de podcast

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7

## Cómo colaborar en tiempo real (Beta)

1. Ve a la página de administración de miembros y crea una invitación.

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="Invitar miembros" /></p>

2. Un compañero de equipo se une y ese espacio de trabajo se vuelve compartido.

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="Flujo de invitación y unión" /></p>

3. Haz que un chat sea compartido y trabajen en él juntos en tiempo real, con comentarios para etiquetar a compañeros.

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeCommentsFlow.gif" alt="Comentarios en tiempo real" /></p>

## SurfSense vs Google NotebookLM

¿Todavía nos comparas como una alternativa a NotebookLM? Aquí tienes el desglose honesto.

| Característica | Google NotebookLM | SurfSense |
|---------|-------------------|-----------|
| **Datos de mercado en vivo para agentes** | No | Conectores de Reddit, YouTube, Google Maps, Google Search y rastreo web vía API REST y MCP |
| **Servidor MCP** | No | Cada conector expuesto como herramienta nativa de agente, más servidores MCP propios con aplicaciones OAuth de un clic |
| **Fuentes por Notebook** | 50 (gratis) a 600 (Ultra, $249.99/mes) | Ilimitadas |
| **Número de Notebooks** | 100 (gratis) a 500 (niveles de pago) | Ilimitado |
| **Límite de tamaño por fuente** | 500,000 palabras / 200MB por fuente | Sin límite |
| **Precios** | Nivel gratuito; Pro $19.99/mes, Ultra $249.99/mes | Gratuito y de código abierto para autoalojar; la nube es de pago por uso con $5 de crédito gratuito |
| **Soporte de LLM** | Solo Google Gemini | Más de 100 LLMs vía la especificación de OpenAI y LiteLLM |
| **Modelos de embeddings** | Solo Google | Más de 6,000 modelos de embeddings, todos los rerankers principales |
| **LLMs locales / privados** | No disponible | Soporte completo (vLLM, Ollama), tus datos siguen siendo tuyos |
| **Autoalojable** | No | Sí, con un solo comando de Docker o Docker Compose completo |
| **Código abierto** | No | Sí |
| **Fuentes de la base de conocimiento** | Google Drive, YouTube, sitios web | Subida de archivos, Google Drive, OneDrive, Dropbox, sincronización de carpetas locales y páginas rastreadas |
| **Formatos de archivo compatibles** | PDFs, Docs, Slides, Sheets, CSV, Word, EPUB, imágenes, URLs web, YouTube | Más de 50 formatos: documentos, imágenes, videos vía LlamaCloud, Unstructured o Docling (local) |
| **Búsqueda** | Búsqueda semántica | Híbrida semántica + texto completo con índices jerárquicos y fusión de rangos recíprocos |
| **Respuestas con citas** | Sí | Sí, respuestas citadas al estilo Perplexity |
| **Arquitectura agéntica** | No | Sí, impulsada por [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) con planificación, subagentes y acceso al sistema de archivos |
| **Automatizaciones y agentes de IA** | No | Flujos de trabajo programados, activadores por eventos y automatizaciones sin código creadas por chat con escritura en Notion, Slack, Linear y Jira |
| **Multijugador en tiempo real** | Notebooks compartidos con roles de Visualizador/Editor (sin chat en tiempo real) | RBAC con roles de Propietario / Administrador / Editor / Visualizador, chat en tiempo real e hilos de comentarios |
| **Generación de video** | Resúmenes de video cinematográficos vía Veo 3 (solo Ultra) | Disponible (NotebookLM es mejor aquí, en mejora activa) |
| **Generación de presentaciones** | Diapositivas más atractivas pero no editables | Presentaciones editables basadas en diapositivas |
| **Generación de podcasts** | Resúmenes de audio con presentadores e idiomas personalizables | Disponible con múltiples proveedores de TTS (NotebookLM es mejor aquí, en mejora activa) |
| **Aplicación de escritorio** | No | Aplicación nativa con General Assist, Quick Assist, Screenshot Assist y sincronización de carpetas locales |

## Solicitudes de funciones y futuro

**SurfSense está en desarrollo activo.** Aunque todavía no está listo para producción, puedes ayudarnos a acelerar el proceso.

¡Únete al [Discord de SurfSense](https://discord.gg/ejRNvftDp9) y ayuda a dar forma al futuro de SurfSense!

## Hoja de ruta

Mantente al día con nuestro progreso de desarrollo y las próximas funciones. Consulta nuestra hoja de ruta pública y aporta tus ideas o comentarios:

**Discusión de la hoja de ruta:** [SurfSense 2026 Roadmap](https://github.com/MODSetter/SurfSense/discussions/565)

**Tablero Kanban:** [SurfSense Project Board](https://github.com/users/MODSetter/projects/3)

## Contribuye

Todas las contribuciones son bienvenidas, desde estrellas y reportes de errores hasta mejoras del backend. Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para comenzar.

Gracias a todos nuestros Surfers:

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" />
</a>

## Historial de estrellas

<a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
 </picture>
</a>

---
---
<p align="center">
    <img 
      src="https://github.com/user-attachments/assets/329c9bc2-6005-4aed-a629-700b5ae296b4" 
      alt="Catalyst Project" 
      width="200"
    />
</p>

---
---
