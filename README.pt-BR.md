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

O NotebookLM é uma das melhores e mais úteis plataformas de IA disponíveis, mas quando você começa a usá-lo regularmente também sente suas limitações deixando algo a desejar.

1. Há limites na quantidade de fontes que você pode adicionar em um notebook.
2. Há limites no número de notebooks que você pode ter.
3. Você não pode ter fontes que excedam 500.000 palavras e mais de 200MB.
4. Você fica preso aos serviços do Google (LLMs, modelos de uso, etc.) sem opção de configurá-los.
5. Fontes de dados externas e integrações de serviços limitadas.
6. O agente do NotebookLM é especificamente otimizado apenas para estudar e pesquisar, mas você pode fazer muito mais com os dados de origem.
7. Falta de suporte multiplayer.

...e mais.

**O SurfSense foi feito especificamente para resolver esses problemas.** O SurfSense permite que você:

- **Controle Seu Fluxo de Dados** - Mantenha seus dados privados e seguros.
- **Sem Limites de Dados** - Adicione uma quantidade ilimitada de fontes e notebooks.
- **Sem Dependência de Fornecedor** - Configure qualquer modelo LLM, de imagem, TTS e STT.
- **25+ Fontes de Dados Externas** - Adicione suas fontes do Google Drive, OneDrive, Dropbox, Notion e muitos outros serviços externos.
- **Suporte Multiplayer em Tempo Real** - Trabalhe facilmente com os membros da sua equipe em um notebook compartilhado.
- **Aplicativo Desktop** - Obtenha assistência de IA em qualquer aplicativo com Quick Assist, General Assist, Extreme Assist e sincronização de pastas locais.

...e mais por vir.



## Exemplo de Agente de Vídeo

https://github.com/user-attachments/assets/012a7ffa-6f76-4f06-9dda-7632b470057a



## Exemplo de Agente de Podcast

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7


## Como Usar o SurfSense

### Cloud

1. Acesse [surfsense.com](https://www.surfsense.com) e faça login.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/LoginFlowGif.gif" alt="Login" /></p>

2. Conecte seus conectores e sincronize. Ative a sincronização periódica para manter os conectores atualizados.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ConnectorFlowGif.gif" alt="Conectores" /></p>

3. Enquanto os dados dos conectores são indexados, faça upload de documentos.

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/DocUploadGif.gif" alt="Upload de Documentos" /></p>

4. Quando tudo estiver indexado, pergunte o que quiser (Casos de uso):

   - Aplicativo Desktop — General Assist

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/general_assist.gif" alt="General Assist" /></p>

   - Aplicativo Desktop — Quick Assist

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/quick_assist.gif" alt="Quick Assist" /></p>

   - Aplicativo Desktop — Extreme Assist

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/extreme_assist.gif" alt="Extreme Assist" /></p>

   - Aplicativo Desktop — Watch Local Folder

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/folder_watch.gif" alt="Watch Local Folder" /></p>

   - Geração de vídeos

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/video_gen_gif.gif" alt="Geração de Vídeos" /></p>

   - Busca básica e citações

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BSNCGif.gif" alt="Busca e Citação" /></p>

   - QNA com menção de documentos

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="QNA com Menção de Documentos" /></p>
   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="QNA com Menção de Documentos" /></p>

   - Geração de relatórios e exportações (PDF, DOCX, HTML, LaTeX, EPUB, ODT, texto simples)

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ReportGenGif_compressed.gif" alt="Geração de Relatórios" /></p>

   - Geração de podcasts

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/PodcastGenGif.gif" alt="Geração de Podcasts" /></p>

   - Geração de imagens

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ImageGenGif.gif" alt="Geração de Imagens" /></p>

   - E mais em breve.


### Auto-Hospedado

Execute o SurfSense na sua própria infraestrutura para controle total de dados e privacidade.

**Pré-requisitos:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) deve estar instalado e em execução.

#### Para usuários de Linux/MacOS:

```bash
curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
```

#### Para usuários do Windows:

```powershell
irm https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.ps1 | iex
```

O script de instalação configura o [Watchtower](https://github.com/nicholas-fedor/watchtower) automaticamente para atualizações diárias. Para pular, adicione a flag `--no-watchtower`.

Para Docker Compose, instalação manual e outras opções de implantação, consulte a [documentação](https://www.surfsense.com/docs/).

### Aplicativo Desktop

O SurfSense também oferece um aplicativo desktop que traz assistência de IA para cada aplicativo no seu computador. Baixe-o na [última versão](https://github.com/MODSetter/SurfSense/releases/latest).

O aplicativo desktop inclui estes recursos poderosos:

- **General Assist** — Abra o SurfSense instantaneamente de qualquer aplicativo com um atalho global.
- **Quick Assist** — Selecione texto em qualquer lugar, depois peça à IA para explicar, reescrever ou agir sobre ele.
- **Extreme Assist** — Receba sugestões de escrita em linha alimentadas pela sua base de conhecimento enquanto digita em qualquer aplicativo.
- **Watch Local Folder** — Monitore uma pasta local e sincronize automaticamente as alterações de arquivos com sua base de conhecimento. **Pro tip:** Aponte para seu cofre do Obsidian para manter suas notas pesquisáveis no SurfSense.

Todos os recursos operam no espaço de busca escolhido, para que suas respostas sejam sempre baseadas nos seus próprios dados.

### Como Colaborar em Tempo Real (Beta)

1. Acesse a página de Gerenciar Membros e crie um convite.

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="Convidar Membros" /></p>

2. O colega aceita e aquele SearchSpace se torna compartilhado.

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="Fluxo de Entrada por Convite" /></p>

3. Torne o chat compartilhado.

   <p align="center"><img src="https://github.com/user-attachments/assets/17b93904-0888-4c3a-ac12-51a24a8ea26a" alt="Tornar Chat Compartilhado" /></p>

4. Sua equipe agora pode conversar em tempo real.

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeChatGif.gif" alt="Chat em Tempo Real" /></p>

5. Adicione comentários para marcar colegas de equipe.

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeCommentsFlow.gif" alt="Comentários em Tempo Real" /></p>

## SurfSense vs Google NotebookLM

| Recurso | Google NotebookLM | SurfSense |
|---------|-------------------|-----------|
| **Fontes por Notebook** | 50 (Grátis) a 600 (Ultra, $249.99/mês) | Ilimitadas |
| **Número de Notebooks** | 100 (Grátis) a 500 (planos pagos) | Ilimitados |
| **Limite de Tamanho da Fonte** | 500.000 palavras / 200MB por fonte | Sem limite |
| **Preços** | Nível gratuito disponível; Pro $19.99/mês, Ultra $249.99/mês | Gratuito e de código aberto, auto-hospedável na sua própria infra |
| **Suporte a LLM** | Apenas Google Gemini | 100+ LLMs via OpenAI spec e LiteLLM |
| **Modelos de Embeddings** | Apenas Google | 6.000+ modelos de embeddings, todos os principais rerankers |
| **LLMs Locais / Privados** | Não disponível | Suporte completo (vLLM, Ollama) - seus dados ficam com você |
| **Auto-Hospedável** | Não | Sim - Docker em um único comando ou Docker Compose completo |
| **Código Aberto** | Não | Sim |
| **Conectores Externos** | Google Drive, YouTube, sites | 27+ conectores - Mecanismos de busca, Google Drive, OneDrive, Dropbox, Slack, Teams, Jira, Notion, GitHub, Discord e [mais](#fontes-externas) |
| **Suporte a Formatos de Arquivo** | PDFs, Docs, Slides, Sheets, CSV, Word, EPUB, imagens, URLs web, YouTube | 50+ formatos - documentos, imagens, vídeos via LlamaCloud, Unstructured ou Docling (local) |
| **Busca** | Busca semântica | Busca Híbrida - Semântica + Texto completo com Índices Hierárquicos e Reciprocal Rank Fusion |
| **Respostas com Citações** | Sim | Sim - Respostas citadas no estilo Perplexity |
| **Arquitetura de Agentes** | Não | Sim - alimentado por [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) com planejamento, subagentes e acesso ao sistema de arquivos |
| **Multiplayer em Tempo Real** | Notebooks compartilhados com papéis de Visualizador/Editor (sem chat em tempo real) | RBAC com papéis de Proprietário / Admin / Editor / Visualizador, chat em tempo real e threads de comentários |
| **Geração de Vídeos** | Visões gerais cinemáticas via Veo 3 (apenas Ultra) | Disponível (NotebookLM é melhor aqui, melhorando ativamente) |
| **Geração de Apresentações** | Slides mais bonitos mas não editáveis | Cria apresentações editáveis baseadas em slides |
| **Geração de Podcasts** | Visões gerais em áudio com hosts e idiomas personalizáveis | Disponível com múltiplos provedores TTS (NotebookLM é melhor aqui, melhorando ativamente) |
| **Aplicativo Desktop** | Não | Aplicativo nativo com General Assist, Quick Assist, Extreme Assist e sincronização de pastas locais |
| **Extensão de Navegador** | Não | Extensão multi-navegador para salvar qualquer página web, incluindo páginas protegidas por autenticação |

<details>
<summary><b>Lista completa de Fontes Externas</b></summary>
<a id="fontes-externas"></a>

Mecanismos de Busca (SearXNG, Tavily, LinkUp, Baidu Search) · Google Drive · OneDrive · Dropbox · Slack · Microsoft Teams · Linear · Jira · ClickUp · Confluence · BookStack · Notion · Gmail · Vídeos do YouTube · GitHub · Discord · Airtable · Google Calendar · Luma · Circleback · Elasticsearch · Obsidian, e mais por vir.

</details>


## SOLICITAÇÕES DE FUNCIONALIDADES E FUTURO


**O SurfSense está em desenvolvimento ativo.** Embora ainda não esteja pronto para produção, você pode nos ajudar a acelerar o processo.

Junte-se ao [Discord do SurfSense](https://discord.gg/ejRNvftDp9) e ajude a moldar o futuro do SurfSense!

## Roadmap

Fique atualizado com nosso progresso de desenvolvimento e próximas funcionalidades!  
Confira nosso roadmap público e contribua com suas ideias ou feedback:

**Discussão do Roadmap:** [SurfSense 2026 Roadmap](https://github.com/MODSetter/SurfSense/discussions/565)

**Quadro Kanban:** [SurfSense Project Board](https://github.com/users/MODSetter/projects/3)


## Contribuir

Todas as contribuições são bem-vindas, desde estrelas e relatórios de bugs até melhorias no backend. Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para começar.

Obrigado a todos os nossos Surfers:

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" />
</a>

## Histórico de Stars

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
