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

# SurfSense
Conecte qualquer LLM às suas fontes de conhecimento internas e converse com ele em tempo real junto com sua equipe. Alternativa de código aberto ao NotebookLM, Perplexity e Glean.

SurfSense é um agente de pesquisa de IA altamente personalizável, conectado a fontes externas como mecanismos de busca (SearxNG, Tavily, LinkUp), Google Drive, Slack, Microsoft Teams, Linear, Jira, ClickUp, Confluence, BookStack, Gmail, Notion, YouTube, GitHub, Discord, Airtable, Google Calendar, Luma, Circleback, Elasticsearch, Obsidian e mais por vir.

<div align="center">
<a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter%2FSurfSense | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>


# Vídeo

https://github.com/user-attachments/assets/cc0c84d3-1f2f-4f7a-b519-2ecce22310b1


## Exemplo de Podcast

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7




## Funcionalidades Principais

### 💡 **Ideia**: 
- Alternativa de código aberto ao NotebookLM, Perplexity e Glean. Conecte qualquer LLM às suas fontes de conhecimento internas e colabore com sua equipe em tempo real.
### 📁 **Suporte a Múltiplos Formatos de Arquivo**
- Salve conteúdo dos seus arquivos pessoais *(Documentos, imagens, vídeos e suporta **mais de 50 extensões de arquivo**)* na sua própria base de conhecimento pessoal.
### 🔍 **Pesquisa Poderosa**
- Pesquise ou encontre rapidamente qualquer coisa no seu conteúdo salvo.
### 💬 **Converse com seu Conteúdo Salvo**
- Interaja em linguagem natural e obtenha respostas com citações.
### 📄 **Respostas com Citações**
- Obtenha respostas com citações como no Perplexity.
### 🧩 **Compatibilidade Universal**
- Conecte virtualmente qualquer provedor de inferência via especificação OpenAI e LiteLLM.
### 🔔 **Privacidade e Suporte a LLM Local**
- Funciona perfeitamente com LLMs locais como vLLM e Ollama.
### 🏠 **Auto-Hospedável**
- Código aberto e fácil de implantar localmente.
### 👥 **Colaboração em Equipe com RBAC**
- Controle de acesso baseado em funções para Espaços de Pesquisa
- Convide membros da equipe com funções personalizáveis (Proprietário, Admin, Editor, Visualizador)
- Permissões granulares para documentos, chats, conectores e configurações
- Compartilhe bases de conhecimento com segurança dentro da sua organização
- Chats de equipe atualizam em tempo real e "Converse sobre o chat" em threads de comentários
### 🎙️ Podcasts
- Agente de geração de podcasts ultrarrápido. (Cria um podcast de 3 minutos em menos de 20 segundos.)
- Converta suas conversas de chat em conteúdo de áudio envolvente
- Suporte para provedores TTS locais (Kokoro TTS)
- Suporte para múltiplos provedores TTS (OpenAI, Azure, Google Vertex AI)

### 🤖 **Arquitetura de Agentes Profundos**
- Alimentado por [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) - agentes que podem planejar, usar subagentes e aproveitar sistemas de arquivos para tarefas complexas.

### 📊 **Técnicas Avançadas de RAG**
- Suporta mais de 100 LLMs
- Suporta mais de 6000 modelos de embeddings
- Suporta todos os principais rerankers (Pinecone, Cohere, Flashrank, etc.)
- Utiliza índices hierárquicos (configuração RAG de 2 níveis)
- Utiliza busca híbrida (Semântica + Texto completo combinado com Reciprocal Rank Fusion)

### ℹ️ **Fontes Externas**
- Mecanismos de busca (Tavily, LinkUp)
- SearxNG (instâncias auto-hospedadas)
- Google Drive
- Slack
- Microsoft Teams
- Linear
- Jira
- ClickUp
- Confluence
- BookStack
- Notion
- Gmail
- Vídeos do YouTube
- GitHub
- Discord
- Airtable
- Google Calendar
- Luma
- Circleback
- Elasticsearch
- Obsidian
- e mais por vir.....

## 📄 **Extensões de Arquivo Suportadas**

| Serviço ETL | Formatos | Notas |
|-------------|----------|-------|
| **LlamaCloud** | 50+ formatos | Documentos, apresentações, planilhas, imagens |
| **Unstructured** | 34+ formatos | Formatos principais + suporte a e-mail |
| **Docling** | Formatos principais | Processamento local, sem necessidade de chave API |

**Áudio/Vídeo** (via serviço STT): `.mp3`, `.wav`, `.mp4`, `.webm`, etc.

### 🔖 Extensão Multi-Navegador
- A extensão do SurfSense pode ser usada para salvar qualquer página web que você desejar.
- Seu principal uso é salvar páginas web protegidas por autenticação.



## SOLICITAÇÕES DE FUNCIONALIDADES E FUTURO


**O SurfSense está em desenvolvimento ativo.** Embora ainda não esteja pronto para produção, você pode nos ajudar a acelerar o processo.

Junte-se ao [Discord do SurfSense](https://discord.gg/ejRNvftDp9) e ajude a moldar o futuro do SurfSense!

## 🚀 Roadmap

Fique atualizado com nosso progresso de desenvolvimento e próximas funcionalidades!  
Confira nosso roadmap público e contribua com suas ideias ou feedback:

**📋 Discussão do Roadmap:** [SurfSense 2025-2026 Roadmap: Deep Agents, Real-Time Collaboration & MCP Servers](https://github.com/MODSetter/SurfSense/discussions/565)

**📊 Quadro Kanban:** [SurfSense Project Board](https://github.com/users/MODSetter/projects/3)


## Como começar?

### Início Rápido com Docker 🐳

> [!TIP]
> Para implantações em produção, use a configuração completa do [Docker Compose](https://www.surfsense.com/docs/docker-installation) que oferece mais controle e escalabilidade.

**Linux/macOS:**

```bash
docker run -d -p 3000:3000 -p 8000:8000 -p 5133:5133 \
  -v surfsense-data:/data \
  --name surfsense \
  --restart unless-stopped \
  ghcr.io/modsetter/surfsense:latest
```

**Windows (PowerShell):**

```powershell
docker run -d -p 3000:3000 -p 8000:8000 -p 5133:5133 `
  -v surfsense-data:/data `
  --name surfsense `
  --restart unless-stopped `
  ghcr.io/modsetter/surfsense:latest
```

**Com Configuração Personalizada:**

Você pode passar qualquer variável de ambiente usando flags `-e`:

```bash
docker run -d -p 3000:3000 -p 8000:8000 -p 5133:5133 \
  -v surfsense-data:/data \
  -e EMBEDDING_MODEL=openai://text-embedding-ada-002 \
  -e OPENAI_API_KEY=your_openai_api_key \
  -e AUTH_TYPE=GOOGLE \
  -e GOOGLE_OAUTH_CLIENT_ID=your_google_client_id \
  -e GOOGLE_OAUTH_CLIENT_SECRET=your_google_client_secret \
  -e ETL_SERVICE=LLAMACLOUD \
  -e LLAMA_CLOUD_API_KEY=your_llama_cloud_key \
  --name surfsense \
  --restart unless-stopped \
  ghcr.io/modsetter/surfsense:latest
```

> [!NOTE]
> - Se estiver implantando atrás de um proxy reverso com HTTPS, adicione `-e BACKEND_URL=https://api.yourdomain.com`

Após iniciar, acesse o SurfSense em:
- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **API Backend**: [http://localhost:8000](http://localhost:8000)
- **Documentação da API**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Electric-SQL**: [http://localhost:5133](http://localhost:5133)

**Comandos Úteis:**

```bash
docker logs -f surfsense      # Ver logs
docker stop surfsense         # Parar
docker start surfsense        # Iniciar
docker rm surfsense           # Remover (dados preservados no volume)
```

### Opções de Instalação

O SurfSense oferece múltiplas opções para começar:

1. **[SurfSense Cloud](https://www.surfsense.com/login)** - A forma mais fácil de experimentar o SurfSense sem nenhuma configuração.
   - Sem necessidade de instalação
   - Acesso instantâneo a todas as funcionalidades
   - Perfeito para começar rapidamente

2. **Início Rápido Docker (Acima)** - Um único comando para ter o SurfSense rodando localmente.
   - Imagem tudo-em-um com PostgreSQL, Redis e todos os serviços incluídos
   - Perfeito para avaliação, desenvolvimento e implantações pequenas
   - Dados persistidos via volume Docker

3. **[Docker Compose (Produção)](https://www.surfsense.com/docs/docker-installation)** - Implantação de stack completo com serviços separados.
   - Inclui pgAdmin para gerenciamento de banco de dados via interface web
   - Suporta personalização de variáveis de ambiente via arquivo `.env`
   - Opções de implantação flexíveis (stack completo ou apenas serviços principais)
   - Melhor para produção com escalamento independente de serviços

4. **[Instalação Manual](https://www.surfsense.com/docs/manual-installation)** - Para usuários que preferem mais controle sobre sua configuração ou precisam personalizar sua implantação.

Os guias de Docker e instalação manual incluem instruções detalhadas específicas para Windows, macOS e Linux.

Antes da instalação auto-hospedada, certifique-se de completar os [passos de configuração prévia](https://www.surfsense.com/docs/) incluindo:
- Configuração de autenticação (opcional - padrão é autenticação LOCAL)
- **Serviço ETL de Processamento de Arquivos** (opcional - padrão é Docling):
  - Docling (padrão, processamento local, sem necessidade de chave API, suporta PDF, documentos Office, imagens, HTML, CSV)
  - Chave API do Unstructured.io (suporta 34+ formatos)
  - Chave API do LlamaIndex (análise aprimorada, suporta 50+ formatos)
- Outras chaves API conforme necessário para seu caso de uso


## Contribuir

Contribuições são muito bem-vindas! Uma contribuição pode ser tão pequena quanto uma ⭐ ou até mesmo encontrar e criar issues.
O ajuste fino do Backend é sempre desejado.

Para diretrizes detalhadas de contribuição, consulte nosso arquivo [CONTRIBUTING.md](CONTRIBUTING.md).

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
