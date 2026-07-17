<a href="https://www.surfsense.com/"><img width="1584" height="396" alt="SurfSense, a plataforma open source de pesquisa na web aberta para agentes de IA" src="https://github.com/user-attachments/assets/9361ef58-1753-4b6e-b275-5020d8847261" /></a>



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

# SurfSense: NotebookLM para Pesquisa na Web Aberta

O SurfSense é a **plataforma open source de pesquisa na web aberta para agentes de IA**, como o NotebookLM, mas com conectores de dados ao vivo. Seus agentes pesquisam a web ao vivo com dados estruturados do **Reddit, YouTube, Instagram, TikTok, Google Maps, Google Search e de qualquer página da web aberta**, por meio de uma única **API REST** ou de um **servidor MCP**. Agentes agendados ou acionados por eventos transformam o que encontram em relatórios e alertas, e uma base de conhecimento integrada mantém cada descoberta pesquisável, com citações.

> [!NOTE]
> **📢 Um recado para nossos usuários que buscavam uma alternativa ao NotebookLM**
>
> Nos últimos meses, construímos o SurfSense como o melhor agente de pesquisa geral para o seu próprio conhecimento, e esse capítulo nos rendeu uma comunidade da qual temos muito orgulho. Ferramentas agênticas como Claude, OpenCode, Hermes e OpenClaw já provaram que os agentes são o futuro, e raciocinar sobre um índice estático está se tornando algo que todo agente capaz faz nativamente. O que ainda falta aos agentes são **dados ao vivo dos lugares onde as respostas realmente vivem, e os fluxos de trabalho em torno deles**. É para lá que estamos direcionando toda a nossa energia: dar aos agentes as primitivas para pesquisar a web aberta.
>
> **Nada do que você usa vai deixar de existir.** Sua base de conhecimento, o chat com citações, os relatórios, os podcasts, as apresentações, as automações e os chats colaborativos continuam funcionando, e a auto-hospedagem segue gratuita e open source. Leia o anúncio completo no [nosso changelog](https://www.surfsense.com/changelog).

## Sumário

- [Por que os agentes precisam do SurfSense](#por-que-os-agentes-precisam-do-surfsense)
- [Conectores de dados ao vivo](#conectores-de-dados-ao-vivo)
- [Início rápido](#início-rápido)
- [Tudo o mais que vem na caixa](#tudo-o-mais-que-vem-na-caixa)
- [Como o SurfSense se compara](#como-o-surfsense-se-compara)
- [Roadmap](#roadmap)
- [Contribua](#contribua)

## Por que os agentes precisam do SurfSense

Pergunte a qualquer agente capaz "o que o Reddit está dizendo sobre este produto desde o lançamento?" ou "do que os reviews destes dez lugares realmente reclamam?" e ele não terá nenhum lugar confiável para procurar. As APIs oficiais das plataformas têm limites de requisições, preços voltados para empresas ou simplesmente não existem; a infraestrutura de scraping é frágil; e controlar um navegador com um LLM queima minutos e tokens por página. O SurfSense, em vez disso, dá aos agentes as primitivas:

- **Uma única superfície tipada para onde quer que os dados estejam.** Cada conector é um endpoint REST que retorna JSON estruturado — posts, comentários, transcrições, reviews, SERPs, páginas. Sem roleta de limites de requisição, sem parsing de HTML, sem loop de navegador.
- **Um servidor MCP** que expõe cada conector como uma ferramenta nativa (`surfsense_reddit_scrape`, `surfsense_google_search` e outras) para o Claude, o Cursor ou qualquer framework de agentes.
- **Um harness de agentes**, não apenas dados brutos: novas tentativas, saída estruturada e medição de créditos já vêm prontos, então os agentes vão de uma pergunta a um relatório com citações sem que você precise construir a infraestrutura.
- **Open source e auto-hospedável**, para que sua pesquisa permaneça na sua própria infraestrutura.

## Conectores de dados ao vivo

| Conector | O que seus agentes recebem | Saiba mais |
|---|---|---|
| **Reddit** | Posts, comentários e fluxos de subreddits sem os limites de requisição da API oficial | [Reddit Scraper API](https://www.surfsense.com/reddit) |
| **YouTube** | Vídeos, transcrições e threads de comentários em escala | [YouTube Scraper API](https://www.surfsense.com/youtube) |
| **Instagram** | Perfis, posts e reels públicos sem a Graph API | [Instagram Scraper API](https://www.surfsense.com/instagram) |
| **TikTok** | Vídeos, comentários, hashtags e perfis sem aprovação da Research API | [TikTok Scraper API](https://www.surfsense.com/tiktok) |
| **Google Maps** | Estabelecimentos, avaliações e reviews para pesquisa de negócios locais | [Google Maps Scraper API](https://www.surfsense.com/google-maps) |
| **Google Search** | SERPs ao vivo para pesquisa e monitoramento de buscas | [Google Search API](https://www.surfsense.com/google-search) |
| **Web Crawl** (rastreamento web) | Qualquer página da web aberta como conteúdo limpo e estruturado | [Web Crawling API](https://www.surfsense.com/web-crawl) |
| **Conectores MCP externos** | Traga qualquer servidor MCP para seus agentes, com OAuth em um clique para Notion, Slack, Jira e outros | [External MCP Connectors](https://www.surfsense.com/external-mcp-connectors) |

O catálogo de conectores está crescendo para além das plataformas sociais e da busca; cada nova fonte chega como um endpoint tipado na mesma API e no mesmo servidor MCP.

A cobrança é por uso: os conectores cobram por item efetivamente retornado, os rastreamentos por página obtida com sucesso, e chamadas com falha nunca são cobradas. Instalações auto-hospedadas rodam com a cobrança desativada. Veja os [preços](https://www.surfsense.com/pricing).

## Início rápido

### Chame um conector a partir do código

Cada conector é um endpoint REST que você pode chamar de qualquer linguagem com a sua chave de API do SurfSense:

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

Cada [página de conector](https://www.surfsense.com/connectors) tem exemplos prontos para copiar e colar em Python, JavaScript, Go, PHP, Ruby, Java e C#.

### Entregue as ferramentas aos seus agentes via MCP

Adicione o servidor MCP do SurfSense ao Claude, ao Cursor ou ao seu próprio framework de agentes:

```json
{
  "mcpServers": {
    "surfsense": {
      "url": "https://mcp.surfsense.com/mcp",
      "headers": { "Authorization": "Bearer ${SURFSENSE_API_KEY}" }
    }
  }
}
```

Seu agente agora pode chamar cada conector como uma ferramenta nativa. Veja a página do [servidor MCP do SurfSense](https://www.surfsense.com/mcp-server) para a lista completa de ferramentas, ou execute o servidor localmente a partir de [`surfsense_mcp`](./surfsense_mcp).

### Use a nuvem

Acesse [surfsense.com](https://www.surfsense.com), faça login e peça ao agente dados da web ao vivo em linguagem natural. Contas novas começam com US$ 5 de crédito gratuito e sem assinatura.

### Auto-hospede gratuitamente

Rode a plataforma inteira, conectores, agentes, automações e o servidor MCP na sua própria infraestrutura. Instalações auto-hospedadas vêm com a cobrança desativada, então scraping, rastreamento e execuções de agentes são limitados apenas pelo seu hardware e pelas chaves de modelo que você trouxer.

**Pré-requisitos:** o [Docker Desktop](https://www.docker.com/products/docker-desktop/) precisa estar instalado e em execução.

Para Linux/macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
```

Para Windows:

```bash
irm https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.ps1 | iex
```

O script de instalação configura o [Watchtower](https://github.com/nicholas-fedor/watchtower) automaticamente para atualizações automáticas diárias. Para pular essa etapa, adicione a flag `--no-watchtower`. Para Docker Compose, instalação manual e outras opções de implantação, consulte a [documentação](https://www.surfsense.com/docs/).

## Tudo o mais que vem na caixa

O workspace de pesquisa que fez do SurfSense a principal alternativa open source ao NotebookLM continua aqui, e tudo o que seus agentes coletam chega até ele.

**Base de conhecimento**

- Envie PDFs, documentos do Office, imagens e áudio, ou sincronize **Google Drive, OneDrive e Dropbox**. Mais de 50 formatos de arquivo suportados.
- Busca híbrida semântica e de texto completo, com respostas citadas no estilo Perplexity.
- Organização de arquivos por IA que classifica automaticamente os documentos por origem, data e tópico.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="Converse com seus PDFs e documentos" /></p>

**Estúdio de entregáveis**

- Gerador de relatórios com IA, com exportação para PDF, DOCX, HTML, LaTeX, EPUB, ODT ou texto simples.
- Podcasts de IA com dois apresentadores a partir de qualquer documento ou pasta em menos de 20 segundos.
- Apresentações de slides editáveis, resumos em vídeo narrados e geração de imagens por IA.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ReportGenGif_compressed.gif" alt="Gerador de Relatórios com IA" /></p>

**Automações**

- Execute turnos completos de agente de forma agendada ou em resposta a eventos, descritos em linguagem natural, com os resultados gravados no Notion, Slack, Linear e Jira.

**Colaboração em equipe**

- Chats de IA colaborativos em tempo real, com comentários e menções.
- RBAC com os papéis de Owner, Admin, Editor e Viewer.

<p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeChatGif.gif" alt="Chat de IA colaborativo" /></p>

**Aplicativo desktop**

Assistência de IA nativa em todos os aplicativos do seu computador. Baixe na [versão mais recente](https://github.com/MODSetter/SurfSense/releases/latest).

- **General Assist**: abra o SurfSense a partir de qualquer aplicativo com um atalho global.
- **Quick Assist**: selecione texto em qualquer lugar e peça à IA para explicar, reescrever ou agir sobre ele.
- **Screenshot Assist**: capture qualquer região da tela e faça perguntas à IA sobre ela.
- **Watch Local Folder** (monitorar pasta local): sincronize automaticamente uma pasta local com a sua base de conhecimento. Aponte para o seu cofre do Obsidian para manter suas notas pesquisáveis.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/quick_assist.gif" alt="Quick Assist" /></p>

**Sem dependência de fornecedor**

- Mais de 100 LLMs via especificação da OpenAI e LiteLLM, incluindo GPT-5.5, Claude Sonnet 5 e Gemini 3.1 Pro.
- Mais de 6.000 modelos de embedding e todos os principais rerankers.
- Suporte completo a LLMs locais e privados (vLLM, Ollama), para que seus dados continuem sendo seus.

## Exemplo do Agente de Vídeo

https://github.com/user-attachments/assets/012a7ffa-6f76-4f06-9dda-7632b470057a

## Exemplo do Agente de Podcast

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7

## Como colaborar em tempo real (Beta)

1. Vá até a página Manage Members e crie um convite.

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="Convidar membros" /></p>

2. Um colega entra e aquele workspace passa a ser compartilhado.

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="Fluxo de entrada por convite" /></p>

3. Torne um chat compartilhado e trabalhem nele juntos em tempo real, com comentários para marcar colegas.

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeCommentsFlow.gif" alt="Comentários em tempo real" /></p>

## Como o SurfSense se compara

O SurfSense é o único produto open source que combina um workspace de pesquisa no estilo NotebookLM para pessoas com primitivas de dados ao vivo para agentes. Veja como isso se compara a cada classe de ferramenta.

**vs agentes de navegador (Browserbase, Browser Use).** Agentes de navegador controlam um navegador real com um LLM no loop — a ferramenta certa quando a tarefa exige clicar, fazer login ou preencher formulários. Mas a maior parte da pesquisa é recuperação somente leitura, e para recuperação o loop de LLM no navegador custa minutos e milhares de tokens por página. Uma chamada de conector do SurfSense é uma única requisição HTTP: segundos, determinística e zero tokens gastos decidindo onde clicar.

**vs APIs de scraping (Firecrawl).** APIs de scraping são ótimas para transformar uma página genérica em markdown, mas um bloco de markdown ainda deixa o seu agente extraindo estrutura da prosa, e elas se degradam em plataformas protegidas contra bots como Reddit, TikTok e Instagram. Os conectores do SurfSense retornam itens estruturados nativos de cada plataforma — posts, comentários, transcrições, reviews — e cobram apenas pelos itens efetivamente retornados; chamadas com falha nunca são cobradas.

**vs APIs de busca (Exa, Tavily, Parallel).** APIs de busca respondem a partir de um índice da web, o que é a ferramenta certa para "encontre páginas sobre X". Elas não conseguem trazer os comentários de uma thread do Reddit, as reações no TikTok, as transcrições do YouTube ou os reviews do Google Maps — os lugares onde a resposta muitas vezes realmente vive.

**vs marketplaces de scrapers (Apify).** Marketplaces oferecem milhares de actors da comunidade, cada um com seu próprio schema, qualidade e preço. O SurfSense é uma única API tipada e um único servidor MCP, com um harness de agentes e um workspace de pesquisa por trás, e é open source.

### SurfSense vs Google NotebookLM

Ainda nos comparando como alternativa ao NotebookLM? Aqui está o comparativo honesto.

| Recurso | Google NotebookLM | SurfSense |
|---------|-------------------|-----------|
| **Dados da web ao vivo para agentes** | Não | Conectores de Reddit, YouTube, Instagram, TikTok, Google Maps, Google Search e rastreamento web via API REST e MCP |
| **Servidor MCP** | Não | Cada conector exposto como ferramenta nativa de agente, além de servidores MCP próprios com apps OAuth em um clique |
| **Fontes por Notebook** | 50 (gratuito) a 600 (Ultra, US$ 249,99/mês) | Ilimitadas |
| **Número de Notebooks** | 100 (gratuito) a 500 (planos pagos) | Ilimitado |
| **Limite de tamanho por fonte** | 500.000 palavras / 200 MB por fonte | Sem limite |
| **Preços** | Plano gratuito; Pro US$ 19,99/mês, Ultra US$ 249,99/mês | Gratuito e open source para auto-hospedar; a nuvem é paga por uso, com US$ 5 de crédito gratuito |
| **Suporte a LLMs** | Apenas Google Gemini | Mais de 100 LLMs via especificação da OpenAI e LiteLLM |
| **Modelos de embedding** | Apenas Google | Mais de 6.000 modelos de embedding, todos os principais rerankers |
| **LLMs locais / privados** | Não disponível | Suporte completo (vLLM, Ollama), seus dados continuam sendo seus |
| **Auto-hospedável** | Não | Sim, com uma linha de Docker ou Docker Compose completo |
| **Open source** | Não | Sim |
| **Fontes da base de conhecimento** | Google Drive, YouTube, sites | Upload de arquivos, Google Drive, OneDrive, Dropbox, sincronização de pasta local e páginas rastreadas |
| **Formatos de arquivo suportados** | PDFs, Docs, Slides, Sheets, CSV, Word, EPUB, imagens, URLs, YouTube | Mais de 50 formatos: documentos, imagens, vídeos via LlamaCloud, Unstructured ou Docling (local) |
| **Busca** | Busca semântica | Híbrida semântica + texto completo, com índices hierárquicos e fusão de rankings recíprocos |
| **Respostas com citações** | Sim | Sim, respostas citadas no estilo Perplexity |
| **Arquitetura agêntica** | Não | Sim, com [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview), incluindo planejamento, subagentes e acesso ao sistema de arquivos |
| **Automações e agentes de IA** | Não | Fluxos agendados, gatilhos por eventos e automações sem código criadas via chat, com gravação no Notion, Slack, Linear e Jira |
| **Multiplayer em tempo real** | Notebooks compartilhados com papéis Viewer/Editor (sem chat em tempo real) | RBAC com papéis Owner / Admin / Editor / Viewer, chat em tempo real e threads de comentários |
| **Geração de vídeo** | Video Overviews cinematográficos via Veo 3 (apenas Ultra) | Disponível (o NotebookLM é melhor aqui, em melhoria contínua) |
| **Geração de apresentações** | Slides mais bonitos, porém não editáveis | Apresentações editáveis baseadas em slides |
| **Geração de podcasts** | Audio Overviews com apresentadores e idiomas personalizáveis | Disponível com vários provedores de TTS (o NotebookLM é melhor aqui, em melhoria contínua) |
| **Aplicativo desktop** | Não | App nativo com General Assist, Quick Assist, Screenshot Assist e sincronização de pasta local |

## Pedidos de recursos e futuro

**O SurfSense está em desenvolvimento ativo.** Embora ainda não esteja pronto para produção, você pode nos ajudar a acelerar o processo.

Entre no [Discord do SurfSense](https://discord.gg/ejRNvftDp9) e ajude a moldar o futuro do SurfSense!

## Roadmap

Fique por dentro do nosso progresso de desenvolvimento e dos próximos recursos. Confira nosso roadmap público e contribua com suas ideias ou feedback:

**Discussão do roadmap:** [SurfSense 2026 Roadmap](https://github.com/MODSetter/SurfSense/discussions/565)

**Quadro Kanban:** [SurfSense Project Board](https://github.com/users/MODSetter/projects/3)

## Contribua

Todas as contribuições são bem-vindas, de estrelas e relatos de bugs a melhorias no backend. Veja o [CONTRIBUTING.md](CONTRIBUTING.md) para começar.

Obrigado a todos os nossos Surfers:

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" />
</a>

## Histórico de estrelas

<a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
   <img alt="Gráfico do histórico de estrelas" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
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
