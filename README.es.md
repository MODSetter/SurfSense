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
Conecta cualquier LLM a tus fuentes de conocimiento internas y chatea con él en tiempo real junto a tu equipo. Alternativa de código abierto a NotebookLM, Perplexity y Glean.

SurfSense es un agente de investigación de IA altamente personalizable, conectado a fuentes externas como motores de búsqueda (SearxNG, Tavily, LinkUp), Google Drive, Slack, Microsoft Teams, Linear, Jira, ClickUp, Confluence, BookStack, Gmail, Notion, YouTube, GitHub, Discord, Airtable, Google Calendar, Luma, Circleback, Elasticsearch, Obsidian y más por venir.



# Video 

https://github.com/user-attachments/assets/cc0c84d3-1f2f-4f7a-b519-2ecce22310b1

## Ejemplo de Podcast

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7


## Cómo usar SurfSense

### Cloud

1. Ve a [surfsense.com](https://www.surfsense.com) e inicia sesión.

<p align="center"><img src="https://github.com/user-attachments/assets/b4df25fe-db5a-43c2-9462-b75cf7f1b707" alt="Login" /></p>

2. Conecta tus conectores y sincroniza. Activa la sincronización periódica para mantenerlos actualizados.

<p align="center"><img src="https://github.com/user-attachments/assets/59da61d7-da05-4576-b7c0-dbc09f5985e8" alt="Conectores" /></p>

3. Mientras se indexan los datos de los conectores, sube documentos.

<p align="center"><img src="https://github.com/user-attachments/assets/d1e8b2e2-9eac-41d8-bdc0-f0cdc405d128" alt="Subir Documentos" /></p>

4. Una vez que todo esté indexado, pregunta lo que quieras (Casos de uso):

   - Búsqueda básica y citaciones

   <p align="center"><img src="https://github.com/user-attachments/assets/81e797a1-e01a-4003-8e60-0a0b3a9789df" alt="Búsqueda y Citación" /></p>

   - QNA con mención de documentos

   <p align="center"><img src="https://github.com/user-attachments/assets/be958295-0a8c-4707-998c-9fe1f1c007be" alt="QNA con Mención de Documentos" /></p>

   - Generación de informes y exportaciones (PDF, DOCX por ahora)

   <p align="center"><img src="https://github.com/user-attachments/assets/9836b7d6-57c9-4951-b61c-68202c9b6ace" alt="Generación de Informes" /></p>

   - Generación de podcasts

   <p align="center"><img src="https://github.com/user-attachments/assets/58c9b057-8848-4e81-aaba-d2c617985d8c" alt="Generación de Podcasts" /></p>

   - Generación de imágenes

   <p align="center"><img src="https://github.com/user-attachments/assets/25f94cb3-18f8-4854-afd9-27b7bfd079cb" alt="Generación de Imágenes" /></p>

   - Y más próximamente.


### Auto-Hospedado

Ejecuta SurfSense en tu propia infraestructura para control total de datos y privacidad.

**Inicio Rápido (Docker en un solo comando):**

```bash
docker run -d -p 3000:3000 -p 8000:8000 -p 5133:5133 -v surfsense-data:/data --name surfsense --restart unless-stopped ghcr.io/modsetter/surfsense:latest
```

Después de iniciar, abre [http://localhost:3000](http://localhost:3000) en tu navegador.

Para Docker Compose, instalación manual y otras opciones de despliegue, consulta la [documentación](https://www.surfsense.com/docs/).

### Cómo Colaborar en Tiempo Real (Beta)

1. Ve a la página de Gestión de Miembros y crea una invitación.

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="Invitar Miembros" /></p>

2. El compañero de equipo se une y ese SearchSpace se comparte.

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="Flujo de Unión por Invitación" /></p>

3. Haz el chat compartido.

   <p align="center"><img src="https://github.com/user-attachments/assets/17b93904-0888-4c3a-ac12-51a24a8ea26a" alt="Hacer Chat Compartido" /></p>

4. Tu equipo ahora puede chatear en tiempo real.

   <p align="center"><img src="https://github.com/user-attachments/assets/83803ac2-fbce-4d93-aae3-85eb85a3053a" alt="Chat en Tiempo Real" /></p>

5. Agrega comentarios para etiquetar a compañeros de equipo.

   <p align="center"><img src="https://github.com/user-attachments/assets/3b04477d-8f42-4baa-be95-867c1eaeba87" alt="Comentarios en Tiempo Real" /></p>

## Funcionalidades Principales

| Funcionalidad | Descripción |
|----------------|-------------|
| Alternativa OSS | Reemplazo directo de NotebookLM, Perplexity y Glean con colaboración en equipo en tiempo real |
| 50+ Formatos de Archivo | Sube documentos, imágenes, videos vía LlamaCloud, Unstructured o Docling (local) |
| Búsqueda Híbrida | Semántica + Texto completo con Índices Jerárquicos y Reciprocal Rank Fusion |
| Respuestas con Citas | Chatea con tu base de conocimiento y obtén respuestas citadas al estilo Perplexity |
| Arquitectura de Agentes Profundos | Impulsado por [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) con planificación, subagentes y acceso al sistema de archivos |
| Soporte Universal de LLM | 100+ LLMs, 6000+ modelos de embeddings, todos los principales rerankers vía OpenAI spec y LiteLLM |
| Privacidad Primero | Soporte completo de LLM local (vLLM, Ollama) tus datos son tuyos |
| Colaboración en Equipo | RBAC con roles de Propietario / Admin / Editor / Visor, chat en tiempo real e hilos de comentarios |
| Generación de Podcasts | Podcast de 3 min en menos de 20 segundos; múltiples proveedores TTS (OpenAI, Azure, Kokoro) |
| Extensión de Navegador | Extensión multi-navegador para guardar cualquier página web, incluyendo páginas protegidas por autenticación |
| 25+ Conectores | Motores de búsqueda, Google Drive, Slack, Teams, Jira, Notion, GitHub, Discord y [más](#fuentes-externas) |
| Auto-Hospedable | Código abierto, Docker en un solo comando o Docker Compose completo para producción |

<details>
<summary><b>Lista completa de Fuentes Externas</b></summary>
<a id="fuentes-externas"></a>

Motores de Búsqueda (Tavily, LinkUp) · SearxNG · Google Drive · Slack · Microsoft Teams · Linear · Jira · ClickUp · Confluence · BookStack · Notion · Gmail · Videos de YouTube · GitHub · Discord · Airtable · Google Calendar · Luma · Circleback · Elasticsearch · Obsidian, y más por venir.

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
