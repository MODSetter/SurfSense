<a href="https://www.surfsense.com/"><img width="1584" height="396" alt="readme_banner" src="https://github.com/user-attachments/assets/9361ef58-1753-4b6e-b275-5020d8847261" /></a>



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

# SurfSense

NotebookLM es una de las mejores y más útiles plataformas de IA que existen, pero una vez que comienzas a usarla regularmente también sientes sus limitaciones dejando algo que desear.

1. Hay límites en la cantidad de fuentes que puedes agregar en un notebook.
2. Hay límites en la cantidad de notebooks que puedes tener.
3. No puedes tener fuentes que excedan 500,000 palabras y más de 200MB.
4. Estás bloqueado con los servicios de Google (LLMs, modelos de uso, etc.) sin opción de configurarlos.
5. Fuentes de datos externas e integraciones de servicios limitadas.
6. El agente de NotebookLM está específicamente optimizado solo para estudiar e investigar, pero puedes hacer mucho más con los datos de origen.
7. Falta de soporte multijugador.

...y más.

**SurfSense está específicamente hecho para resolver estos problemas.** SurfSense te permite:

- **Controla Tu Flujo de Datos** - Mantén tus datos privados y seguros.
- **Sin Límites de Datos** - Agrega una cantidad ilimitada de fuentes y notebooks.
- **Sin Dependencia de Proveedores** - Configura cualquier modelo LLM, de imagen, TTS y STT.
- **25+ Fuentes de Datos Externas** - Agrega tus fuentes desde Google Drive, OneDrive, Dropbox, Notion y muchos otros servicios externos.
- **Soporte Multijugador en Tiempo Real** - Trabaja fácilmente con los miembros de tu equipo en un notebook compartido.
- **Aplicación de Escritorio** - Obtén asistencia de IA en cualquier aplicación con Quick Assist, General Assist, Extreme Assist y sincronización de carpetas locales.

...y más por venir.



## Ejemplo de Agente de Video

https://github.com/user-attachments/assets/012a7ffa-6f76-4f06-9dda-7632b470057a



## Ejemplo de Agente de Podcast

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7


## Cómo usar SurfSense

### Cloud

1. Ve a [surfsense.com](https://www.surfsense.com) e inicia sesión.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/LoginFlowGif.gif" alt="Login" /></p>

2. Conecta tus conectores y sincroniza. Activa la sincronización periódica para mantenerlos actualizados.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ConnectorFlowGif.gif" alt="Conectores" /></p>

3. Mientras se indexan los datos de los conectores, sube documentos.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/DocUploadGif.gif" alt="Subir Documentos" /></p>

4. Una vez que todo esté indexado, pregunta lo que quieras (Casos de uso):

   - Aplicación de Escritorio — General Assist

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/general_assist.gif" alt="General Assist" /></p>

   - Aplicación de Escritorio — Quick Assist

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/quick_assist.gif" alt="Quick Assist" /></p>

   - Aplicación de Escritorio — Extreme Assist

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/extreme_assist.gif" alt="Extreme Assist" /></p>

   - Aplicación de Escritorio — Watch Local Folder

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/folder_watch.gif" alt="Watch Local Folder" /></p>

   - Generación de videos

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/video_gen_gif.gif" alt="Generación de Videos" /></p>

   - Búsqueda básica y citaciones

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BSNCGif.gif" alt="Búsqueda y Citación" /></p>

   - QNA con mención de documentos

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="QNA con Mención de Documentos" /></p>
   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="QNA con Mención de Documentos" /></p>

   - Generación de informes y exportaciones (PDF, DOCX, HTML, LaTeX, EPUB, ODT, texto plano)

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ReportGenGif_compressed.gif" alt="Generación de Informes" /></p>

   - Generación de podcasts

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/PodcastGenGif.gif" alt="Generación de Podcasts" /></p>

   - Generación de imágenes

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ImageGenGif.gif" alt="Generación de Imágenes" /></p>

   - Y más próximamente.


### Auto-Hospedado

Ejecuta SurfSense en tu propia infraestructura para control total de datos y privacidad.

**Requisitos previos:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) debe estar instalado y en ejecución.

#### Para usuarios de Linux/MacOS:

```bash
curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
```

#### Para usuarios de Windows:

```powershell
irm https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.ps1 | iex
```

El script de instalación configura [Watchtower](https://github.com/nicholas-fedor/watchtower) automáticamente para actualizaciones diarias. Para omitirlo, agrega la bandera `--no-watchtower`.

Para Docker Compose, instalación manual y otras opciones de despliegue, consulta la [documentación](https://www.surfsense.com/docs/).

### Aplicación de Escritorio

SurfSense también ofrece una aplicación de escritorio que lleva la asistencia de IA a cada aplicación en tu computadora. Descárgala desde la [última versión](https://github.com/MODSetter/SurfSense/releases/latest).

La aplicación de escritorio incluye estas potentes funciones:

- **General Assist** — Lanza SurfSense al instante desde cualquier aplicación con un atajo global.
- **Quick Assist** — Selecciona texto en cualquier lugar, luego pide a la IA que lo explique, reescriba o actúe sobre él.
- **Extreme Assist** — Obtén sugerencias de escritura en línea impulsadas por tu base de conocimiento mientras escribes en cualquier aplicación.
- **Watch Local Folder** — Vigila una carpeta local y sincroniza automáticamente los cambios de archivos con tu base de conocimiento. **Pro tip:** Apúntalo a tu bóveda de Obsidian para mantener tus notas buscables en SurfSense.

Todas las funciones operan contra tu espacio de búsqueda elegido, por lo que tus respuestas siempre están basadas en tus propios datos.

### Cómo Colaborar en Tiempo Real (Beta)

1. Ve a la página de Gestión de Miembros y crea una invitación.

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="Invitar Miembros" /></p>

2. El compañero de equipo se une y ese SearchSpace se comparte.

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="Flujo de Unión por Invitación" /></p>

3. Haz el chat compartido.

   <p align="center"><img src="https://github.com/user-attachments/assets/17b93904-0888-4c3a-ac12-51a24a8ea26a" alt="Hacer Chat Compartido" /></p>

4. Tu equipo ahora puede chatear en tiempo real.

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeChatGif.gif" alt="Chat en Tiempo Real" /></p>

5. Agrega comentarios para etiquetar a compañeros de equipo.

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeCommentsFlow.gif" alt="Comentarios en Tiempo Real" /></p>

## SurfSense vs Google NotebookLM

| Característica | Google NotebookLM | SurfSense |
|---------|-------------------|-----------|
| **Fuentes por Notebook** | 50 (Gratis) a 600 (Ultra, $249.99/mes) | Ilimitadas |
| **Número de Notebooks** | 100 (Gratis) a 500 (planes de pago) | Ilimitados |
| **Límite de Tamaño de Fuente** | 500,000 palabras / 200MB por fuente | Sin límite |
| **Precios** | Nivel gratuito disponible; Pro $19.99/mes, Ultra $249.99/mes | Gratuito y de código abierto, auto-hospedable en tu propia infra |
| **Soporte de LLM** | Solo Google Gemini | 100+ LLMs vía OpenAI spec y LiteLLM |
| **Modelos de Embeddings** | Solo Google | 6,000+ modelos de embeddings, todos los principales rerankers |
| **LLMs Locales / Privados** | No disponible | Soporte completo (vLLM, Ollama) - tus datos son tuyos |
| **Auto-Hospedable** | No | Sí - Docker en un solo comando o Docker Compose completo |
| **Código Abierto** | No | Sí |
| **Conectores Externos** | Google Drive, YouTube, sitios web | 27+ conectores - Motores de búsqueda, Google Drive, OneDrive, Dropbox, Slack, Teams, Jira, Notion, GitHub, Discord y [más](#fuentes-externas) |
| **Soporte de Formatos de Archivo** | PDFs, Docs, Slides, Sheets, CSV, Word, EPUB, imágenes, URLs web, YouTube | 50+ formatos - documentos, imágenes, videos vía LlamaCloud, Unstructured o Docling (local) |
| **Búsqueda** | Búsqueda semántica | Búsqueda Híbrida - Semántica + Texto completo con Índices Jerárquicos y Reciprocal Rank Fusion |
| **Respuestas con Citas** | Sí | Sí - Respuestas citadas al estilo Perplexity |
| **Arquitectura de Agentes** | No | Sí - impulsado por [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) con planificación, subagentes y acceso al sistema de archivos |
| **Multijugador en Tiempo Real** | Notebooks compartidos con roles de Visor/Editor (sin chat en tiempo real) | RBAC con roles de Propietario / Admin / Editor / Visor, chat en tiempo real e hilos de comentarios |
| **Generación de Videos** | Resúmenes en video cinemáticos vía Veo 3 (solo Ultra) | Disponible (NotebookLM es mejor aquí, mejorando activamente) |
| **Generación de Presentaciones** | Diapositivas más atractivas pero no editables | Crea presentaciones editables basadas en diapositivas |
| **Generación de Podcasts** | Resúmenes de audio con hosts e idiomas personalizables | Disponible con múltiples proveedores TTS (NotebookLM es mejor aquí, mejorando activamente) |
| **Aplicación de Escritorio** | No | Aplicación nativa con General Assist, Quick Assist, Extreme Assist y sincronización de carpetas locales |
| **Extensión de Navegador** | No | Extensión multi-navegador para guardar cualquier página web, incluyendo páginas protegidas por autenticación |

<details>
<summary><b>Lista completa de Fuentes Externas</b></summary>
<a id="fuentes-externas"></a>

Motores de Búsqueda (SearXNG, Tavily, LinkUp, Baidu Search) · Google Drive · OneDrive · Dropbox · Slack · Microsoft Teams · Linear · Jira · ClickUp · Confluence · BookStack · Notion · Gmail · Videos de YouTube · GitHub · Discord · Airtable · Google Calendar · Luma · Circleback · Elasticsearch · Obsidian, y más por venir.

</details>


## SOLICITUDES DE FUNCIONES Y FUTURO


**SurfSense está en desarrollo activo.** Aunque aún no está listo para producción, puedes ayudarnos a acelerar el proceso.

¡Únete al [Discord de SurfSense](https://discord.gg/ejRNvftDp9) y ayuda a dar forma al futuro de SurfSense!

## Hoja de Ruta

¡Mantente al día con nuestro progreso de desarrollo y próximas funcionalidades!  
Consulta nuestra hoja de ruta pública y contribuye con tus ideas o comentarios:

**Discusión de la Hoja de Ruta:** [SurfSense 2026 Roadmap](https://github.com/MODSetter/SurfSense/discussions/565)

**Tablero Kanban:** [SurfSense Project Board](https://github.com/users/MODSetter/projects/3)


## Contribuir

Todas las contribuciones son bienvenidas, desde estrellas y reportes de bugs hasta mejoras del backend. Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para comenzar.

Gracias a todos nuestros Surfers:

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" />
</a>

## Historial de Stars

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
