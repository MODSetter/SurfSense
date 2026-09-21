<!--
  El aviso del cierre del servicio alojado tiene fecha de caducidad. Elimínalo
  el 18 de octubre de 2026, cuando se cierre la ventana de exportación, junto
  con el enlace "Importar desde la aplicación alojada" que aparece más abajo.
  Este archivo sigue a README.md sección por sección.
  Justificación de esta página: plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Forks](https://img.shields.io/github/forks/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/network/members)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img width="128" height="128" alt="SurfSense, la alternativa de código abierto a NotebookLM, aislada de la red" src="surfsense_web/public/homepage/icon.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>La alternativa de código abierto a NotebookLM, aislada de la red.</b>
    <br />
    Convierte los documentos que no puedes subir a la nube en resúmenes ejecutivos, presentaciones, informes, guías de estudio y pódcast, íntegramente en tu propio equipo.
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>Descargar</b></a> ·
    <a href="https://www.surfsense.com/docs">Documentación</a> ·
    <a href="#lo-que-crea-surfsense">Qué crea</a> ·
    <a href="#cómo-se-compara-surfsense">Comparativa</a> ·
    <a href="https://www.surfsense.com/pricing">Precios</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | Español | <a href="README.pt-BR.md">Português</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

<p align="center">
  <img src="surfsense_web/public/homepage/offline-studio.png" alt="La aplicación de escritorio SurfSense con Studio abierto y Qwen seleccionado, convirtiendo fuentes locales en artefactos" />
</p>

SurfSense es una aplicación de escritorio gratuita y de código abierto para los documentos que ya tienes. Arrástralos a la aplicación, haz preguntas y obtén respuestas que citan sus fuentes; después convierte esos mismos documentos en un resumen ejecutivo, una presentación, un informe, una guía de estudio o un pódcast. Todo se ejecuta en tu propio equipo: el índice está en tu disco, tú eliges el modelo y la aplicación no sube nada. No hay ninguna cuenta que crear.

**Cómo empezar.** Descarga el instalador para tu equipo y luego usa tu propia clave de modelo o deja que la aplicación descargue un modelo local por ti.

| Plataforma | Descarga |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-Setup.exe) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-arm64.dmg) |
| **Linux** x64 (AppImage) | [SurfSense.AppImage](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.AppImage) |
| **Linux** x64 (deb) | [SurfSense.deb](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.deb) |

Todos los enlaces son permanentes y apuntan a la versión más reciente. También puedes elegir desde [surfsense.com/downloads](https://www.surfsense.com/downloads) o revisar [todas las versiones](https://github.com/MODSetter/SurfSense/releases). El AppImage se actualiza solo; el deb no.

> [!NOTE]
> **¿Usabas la aplicación web alojada?** Se va a retirar. Ábrela una última vez para exportar tus espacios de trabajo y luego importa el paquete en la aplicación de escritorio: documentos, carpetas, títulos e hilos de chat, todo se migra. La ventana de exportación se cierra el 18 de octubre de 2026. Más detalles en [la página del cierre](https://www.surfsense.com/sunset).

## Lo que crea SurfSense

Elige unos cuantos documentos y un formato. La aplicación lo redacta a partir de las fuentes que seleccionaste, en tu equipo.

| Formato | Qué obtienes | Requiere |
|---|---|---|
| **Resumen** | Un informe estructurado de las fuentes seleccionadas | modelo de generación |
| **Tarjetas de estudio** | Un mazo interactivo, una tarjeta a la vez | modelo de generación |
| **Cuestionario** | Preguntas de opción múltiple con sus respuestas | modelo de generación |
| **Mapa mental** | Un Markmap con zoom y nodos plegables | modelo de generación |
| **Diapositivas** | Un `.pptx` editable, no una imagen de una presentación | modelo de generación |
| **Documento** | Un informe `.docx` editable | modelo de generación |
| **Hoja de cálculo** | Un `.xlsx` con las tablas extraídas de las fuentes | modelo de generación |
| **Página web** | Una página HTML autónoma | modelo de generación |
| **PDF** | Un PDF ya maquetado | modelo de generación |
| **Pódcast** | Una conversación de audio entre dos presentadores, con voz generada sin conexión por Kokoro-82M | modelo de generación + voz incluida |
| **Imagen** | Una ilustración para el material | modelo de imagen + modelo de generación |
| **Infografía** | Un resumen visual de un solo panel | modelo de imagen + modelo de generación |

Algunos encargos necesitan más de uno. Una guía de estudio es un resumen, un mazo de tarjetas y un cuestionario sobre el mismo conjunto de fuentes, y un informe para un cliente suele ser la presentación que expones, más el resumen que envías después. Los resúmenes en video todavía no están disponibles.

## Todo se queda en tu equipo

La gente lo usa con expedientes de casos, papeles de trabajo de clientes, transcripciones de entrevistas, especificaciones internas, investigación sin publicar y los apuntes de todo un semestre. Puedes hacer preguntas sobre todo ese material y cada respuesta cita la fuente de la que salió. La aplicación no sube nada de eso.

- **El índice es local.** El análisis, la fragmentación y el cálculo de embeddings ocurren en tu equipo, sobre SQLite en `~/.surfsense`. SurfSense no guarda ninguna copia ni ningún registro de lo que preguntaste.
- **Cada componente puede ejecutarse en local.** El analizador de documentos, el modelo de recuperación y la voz del pódcast vienen dentro del instalador. El chat y la generación de imágenes vienen como servidores locales cuyos pesos descargas una sola vez, así que puedes producir texto, audio e imágenes sin cuenta ni clave de API. Lo probamos indexando un PDF con la red desactivada.
- **Las conexiones salientes están desactivadas por defecto.** Un panel de salida enumera todos los destinos a los que la aplicación puede conectarse y tú activas los que quieras.
- **Sin telemetría ni informes de fallos.** Nada se comunica con el exterior, así que no hay ninguna casilla que desmarcar.

SurfSense no puede decirte si eso cumple con una normativa concreta. Eso depende de tus propios controles y de tu regulador. Lo único que la aplicación puede decirte es en qué equipo están tus documentos.

## Cómo se compara SurfSense

A tres tipos de producto se les llama «el NotebookLM local», y cada uno responde a una pregunta distinta. Ninguno de los tres es una mala herramienta; simplemente te dejan con cosas distintas.

**vs Jan, AnythingLLM, Open WebUI, LM Studio.** Estas ejecutan un modelo en local y te dan un sitio donde conversar con él. SurfSense responde a la pregunta siguiente: ¿cómo sacas de ahí un documento terminado? Puedes usarlas juntas si quieres, apuntando SurfSense a cualquier endpoint compatible con OpenAI, incluido uno de los suyos.

**vs RemNote, Quizlet, NoteGPT, StudyFetch, Gamma.** Estas sí generan entregables, y algunos se ven mejor que los nuestros. A cambio, tu material acaba en otro sitio: lo subes, pagas una cuota mensual y tus archivos viven en la cuenta de otra persona.

**vs Google NotebookLM.** Ya ofrece tarjetas de estudio, cuestionarios, mapas mentales y resúmenes en audio, así que ambos producen prácticamente lo mismo. La diferencia está en qué equipo hace el trabajo y qué modelo puedes ponerle detrás.

| | Google NotebookLM | SurfSense |
|---|---|---|
| Funciona sin conexión / aislado de la red | No | **Sí** |
| Tus documentos salen de tu equipo | Sí | **No** |
| Cuenta obligatoria | Cuenta de Google | **Ninguna** |
| Código abierto | No | **Apache-2.0** |
| Precio | Nivel gratuito; Pro $19.99/mes; Ultra $249.99/mes | **La aplicación es gratuita** |
| Modelos | Solo Gemini | Cualquier API compatible con OpenAI, o una local |
| Límites de fuentes | De 50 a 600 fuentes, 500.000 palabras cada una | Lo que quepa en tu disco |
| Resúmenes en audio y video | Sí, y mejores | Audio sí, sin conexión; video todavía no |

NotebookLM gana en calidad de audio y tiene video. Si no te importa que tus fuentes vivan en los servidores de Google, úsalo. Si no es así, esto es la misma clase de herramienta pero sin subir nada.

## Inicio rápido

No necesitas Docker, ni una terminal, ni una GPU, ni un archivo de compose.

1. **Descarga el instalador** de la tabla de arriba. Está firmado, así que tu sistema operativo no te pondrá trabas.
2. **Elige un modelo.** Deja que la aplicación descargue uno local (Qwen3 en seis tamaños, desde 0,5 GB) o pega la URL base y la clave de cualquier API compatible con OpenAI. El selector comprueba que tu equipo puede ejecutar un modelo antes de ofrecértelo, y cualquier clave que le des se guarda cifrada, con el secreto en el llavero de tu sistema operativo.
3. **Añade tus documentos.** La aplicación procesa archivos PDF, documentos de Office e imágenes en tu equipo.
4. **Haz preguntas.** Cada respuesta cita la fuente de la que salió.
5. **Abre Studio,** elige un formato y recoge el archivo.

La descarga es la parte lenta, porque el instalador lleva el analizador, el modelo de recuperación, la voz del pódcast y los servidores de modelos locales, para que la aplicación funcione con la red apagada.

## Documentación, hoja de ruta y comunidad

La aplicación y sus actualizaciones son gratuitas. Una licencia añade complementos y soporte prioritario, y no restringe nada más: una licencia caducada te deja igualmente la aplicación y todas las actualizaciones futuras. Consulta los [precios](https://www.surfsense.com/pricing).

El stack de Docker de este repositorio (`surfsense_backend`, `surfsense_web`, archivos de compose) sigue siendo de código abierto e instalable, y tiene **soporte de la comunidad: sin SLA y sin ningún servicio alojado detrás.** La aplicación de escritorio es la vía con soporte para los usuarios nuevos.

- [Documentación](https://www.surfsense.com/docs) sobre instalación, modelos, formatos de Studio y autoalojamiento
- [Importar desde la aplicación alojada](https://www.surfsense.com/sunset)
- [Servidor MCP](./surfsense_mcp) para la API de scraping alojada
- [Discusión de la hoja de ruta](https://github.com/MODSetter/SurfSense/discussions/565) y el [tablero del proyecto](https://github.com/users/MODSetter/projects/3)
- [Discord](https://discord.gg/ejRNvftDp9) para ayuda e ideas, [Discussions](https://github.com/MODSetter/SurfSense/discussions) para el rumbo del proyecto, [Issues](https://github.com/MODSetter/SurfSense/issues) para errores reproducibles
- **Dale una estrella al repositorio** si quieres seguir de cerca a dónde va esto

Los pull requests son bienvenidos. Empieza por [CONTRIBUTING.md](CONTRIBUTING.md); la aplicación de escritorio vive en [`surfsense_local/`](./surfsense_local) y su README explica el ciclo de desarrollo.

Gracias a todos nuestros Surfers:

<p align="center">
  <a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="Personas que contribuyen a SurfSense" />
  </a>
</p>

## Historial de estrellas

<p align="center">
  <a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
    </picture>
  </a>
</p>

## Licencia

Apache-2.0. Consulta el archivo [LICENSE](LICENSE).
