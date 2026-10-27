<!--
  O aviso de encerramento tem prazo: remova-o em 18 de outubro de 2026,
  junto com o mesmo aviso no README.md.
  Este arquivo acompanha o README.md seção por seção.
  Justificativa: plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img alt="SurfSense, a alternativa open source ao NotebookLM, isolada da rede" src="www/public/homepage/banner.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>A alternativa open source ao NotebookLM, isolada da rede.</b>
    <br />
    O agente de IA que pesquisa, transforma e edita seus documentos, na sua máquina.
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>Baixar</b></a> ·
    <a href="#o-que-ele-faz-com-cada-formato">Formatos</a> ·
    <a href="#início-rápido">Início rápido</a> ·
    <a href="#como-ele-se-compara">Comparativo</a> ·
    <a href="#plugins">Plugins</a> ·
    <a href="https://www.surfsense.com/pricing">Preços</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | Português | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

**Revise um contrato com alterações controladas e comentários**

https://github.com/user-attachments/assets/88326b9d-e763-46db-9635-75f9df9e8682

**Adicione fontes da web e transforme-as em uma página web**

https://github.com/user-attachments/assets/073577b7-f055-4f59-8540-330bd764aeb0

O SurfSense é um aplicativo de desktop gratuito e open source para os documentos que você não pode enviar para a nuvem. É um agente de IA no estilo do NotebookLM, focado em privacidade, que pesquisa, transforma e edita seus documentos na sua máquina. O índice fica no seu disco, você escolhe o modelo, local ou remoto, e não há conta para criar.

| Plataforma | Download |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://www.surfsense.com/downloads/windows?src=readme) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://www.surfsense.com/downloads/mac?src=readme) |
| **Linux** x64 | [AppImage](https://www.surfsense.com/downloads/linux-appimage?src=readme) · [deb](https://www.surfsense.com/downloads/linux-deb?src=readme) |

## Início rápido

1. Instale o SurfSense e faça a configuração inicial.
2. Solte seus arquivos ou pastas nas suas fontes.
3. Peça ao agente para pesquisar nos seus arquivos, extrair conteúdo deles ou editá-los.

## O que ele faz com cada formato

| Formato | Pesquisar (respostas com citações) | Criar | Editar (em uma cópia) | Transformar |
|---|---|---|---|---|
| **PDF** | ✓ inclusive páginas digitalizadas³ | ✓ | Preencher e achatar formulários; carimbar marcas d'água, números de página, cabeçalhos e rodapés | Mesclar, dividir, extrair, girar e reordenar páginas |
| **Word** `.docx` | ✓ | ✓ ou a partir do seu próprio `.docx` como modelo | ✓ corpo do texto, como alterações controladas e comentários | Para PDF¹ |
| **Excel** `.xlsx` | ✓ o agente também lê as fórmulas | ✓ com fórmulas e gráficos nativos | ✓ valores das células e fórmulas | Analisar com pandas e gerar gráficos dos resultados |
| **PowerPoint** `.pptx` | ✓ | ✓ ou a partir do seu próprio `.pptx` como modelo | Substituir texto nos slides e nas anotações; excluir ou duplicar slides | Para PDF¹ |
| **CSV** | ✓ | — | — | Analisar com pandas e gerar gráficos dos resultados |
| **Imagens** PNG, JPEG, TIFF, BMP, WebP | ✓ texto lido por OCR³ | Imagens e infográficos² | — | Inserir em novos documentos |
| **Markdown**, texto simples | ✓ | ✓ Markdown | — | — |
| **HTML** | ✓ | ✓ página web | — | — |
| **Gravações** WAV, MP3, FLAC, Ogg Vorbis | ✓ transcritas na sua máquina | — | — | — |
| **Podcast** (áudio) | — | ✓ com transcrição; por padrão, a voz é gerada na sua máquina | — | — |
| **Mapas mentais, flashcards, quizzes** | — | ✓ no aplicativo | — | — |

<sub>¹ Com o suporte ao Office (LibreOffice) ativado em Configurações; ele nunca vem no instalador. ² Precisa de um modelo de imagem, local ou remoto; nenhum é escolhido por padrão. ³ O OCR lê escrita latina, chinesa e japonesa.</sub>

Edições, conversões e ferramentas de PDF sempre geram um arquivo novo; o seu original nunca é alterado. Hoje, PDF, Word e Excel são os formatos com mais recursos, e o suporte aos demais formatos continua melhorando.

## Plugins

Conecte-os em **Configurações › Plugins**.

**Da SurfSense.** Eles leem páginas públicas sem usar suas próprias contas e precisam de uma licença do SurfSense: [baixe o aplicativo](https://www.surfsense.com/downloads) e informe seu e-mail nele para receber uma licença gratuita de 14 dias.

| Plugin | O que faz |
|---|---|
| **Google Search** | Pesquisar no Google e ler os resultados, os anúncios e as perguntas relacionadas |
| **Web Crawl** | Ler uma página web ou rastrear um site inteiro e transformá-lo em texto limpo |
| **YouTube** | Ler vídeos, canais e comentários do YouTube |
| **TikTok** | Ler vídeos e comentários do TikTok, pesquisar usuários e ver o que está em alta |
| **Reddit** | Ler posts públicos do Reddit com seus comentários, ou uma comunidade inteira |
| **Instagram** | Ler perfis, posts e reels públicos do Instagram, e pesquisar perfis |
| **Google Maps** | Encontrar lugares no Google Maps e ler as avaliações deles |
| **Amazon** | Ler produtos e resultados de pesquisa da Amazon |
| **Walmart** | Ler produtos, resultados de pesquisa e avaliações do Walmart |
| **Indeed** | Ler vagas de emprego no Indeed |

**De terceiros.** Servidores MCP do [registro de plugins](backend/plugins/registry), como DeepWiki e Notion, ou qualquer servidor que você adicione por URL. Não precisam de licença e ficam desativados até você permitir.

## Como ele se compara

| | NotebookLM (agora Gemini Notebook) | SurfSense |
|---|---|---|
| Roda offline / isolado da rede | Não | **Sim** |
| Seus documentos saem da sua máquina | Sim | **Não**, a menos que você escolha um modelo remoto |
| Pode editar seus arquivos | Não | **Sim** |
| Open source | Não | **Apache-2.0** |
| Modelos | Apenas Gemini | Qualquer API compatível com a OpenAI, ou uma local |

## Comunidade

- [Discord](https://discord.gg/ejRNvftDp9) para ajuda, [Issues](https://github.com/MODSetter/SurfSense/issues) para bugs e [Discussions](https://github.com/MODSetter/SurfSense/discussions) para ideias.
- **Como contribuir:** os PRs vão para `dev`; veja o [CONTRIBUTING.md](CONTRIBUTING.md) e [`surfsense_local/`](./surfsense_local) para o ciclo de desenvolvimento. Em [`docs/`](docs/README.md) está explicado como ele funciona.

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors"><img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="Pessoas que contribuem com o SurfSense" /></a>

## Licença

Apache-2.0. Veja o arquivo [LICENSE](LICENSE).
