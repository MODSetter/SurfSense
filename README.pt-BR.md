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
Conecte qualquer LLM às suas fontes de conhecimento internas e converse com ele em tempo real junto com sua equipe. Alternativa de código aberto ao NotebookLM, Perplexity e Glean.

SurfSense é um agente de pesquisa de IA altamente personalizável, conectado a fontes externas como mecanismos de busca (SearxNG, Tavily, LinkUp), Google Drive, OneDrive, Dropbox, Slack, Microsoft Teams, Linear, Jira, ClickUp, Confluence, BookStack, Gmail, Notion, YouTube, GitHub, Discord, Airtable, Google Calendar, Luma, Circleback, Elasticsearch, Obsidian e mais por vir.



# Demo

https://github.com/user-attachments/assets/cc0c84d3-1f2f-4f7a-b519-2ecce22310b1

## Exemplo de Agente de Vídeo


https://github.com/user-attachments/assets/cc977e6d-8292-4ffe-abb8-3b0560ef5562



## Exemplo de Agente de Podcast

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7


## Como Usar o SurfSense

### Cloud

1. Acesse [surfsense.com](https://www.surfsense.com) e faça login.

<p align="center"><img src="https://github.com/user-attachments/assets/b4df25fe-db5a-43c2-9462-b75cf7f1b707" alt="Login" /></p>

2. Conecte seus conectores e sincronize. Ative a sincronização periódica para manter os conectores atualizados.

<p align="center"><img src="https://github.com/user-attachments/assets/0740f351-23fa-4909-9880-70aa1dcc1df7" alt="Conectores" /></p>

3. Enquanto os dados dos conectores são indexados, faça upload de documentos.

<p align="center"><img src="https://github.com/user-attachments/assets/daf3dbae-ef86-4e86-82ea-fcbcad988761" alt="Upload de Documentos" /></p>

4. Quando tudo estiver indexado, pergunte o que quiser (Casos de uso):

   - Geração de vídeos

   <p align="center"><img src="https://github.com/user-attachments/assets/af85c0f3-6cfd-4757-9706-07fd5e32c857" alt="Geração de Vídeos" /></p>
   
   - Busca básica e citações

   <p align="center"><img src="https://github.com/user-attachments/assets/81e797a1-e01a-4003-8e60-0a0b3a9789df" alt="Busca e Citação" /></p>

   - QNA com menção de documentos

   <p align="center"><img src="https://github.com/user-attachments/assets/65c3bf06-1d46-4dd5-b169-4d934c9b6798" alt="QNA com Menção de Documentos" /></p>
   <p align="center"><img src="https://github.com/user-attachments/assets/be958295-0a8c-4707-998c-9fe1f1c007be" alt="QNA com Menção de Documentos" /></p>

   - Geração de relatórios e exportações (PDF, DOCX, HTML, LaTeX, EPUB, ODT, texto simples)

   <p align="center"><img src="https://github.com/user-attachments/assets/9836b7d6-57c9-4951-b61c-68202c9b6ace" alt="Geração de Relatórios" /></p>

   - Geração de podcasts

   <p align="center"><img src="https://github.com/user-attachments/assets/58c9b057-8848-4e81-aaba-d2c617985d8c" alt="Geração de Podcasts" /></p>

   - Geração de imagens

   <p align="center"><img src="https://github.com/user-attachments/assets/25f94cb3-18f8-4854-afd9-27b7bfd079cb" alt="Geração de Imagens" /></p>

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

### Como Colaborar em Tempo Real (Beta)

1. Acesse a página de Gerenciar Membros e crie um convite.

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="Convidar Membros" /></p>

2. O colega aceita e aquele SearchSpace se torna compartilhado.

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="Fluxo de Entrada por Convite" /></p>

3. Torne o chat compartilhado.

   <p align="center"><img src="https://github.com/user-attachments/assets/17b93904-0888-4c3a-ac12-51a24a8ea26a" alt="Tornar Chat Compartilhado" /></p>

4. Sua equipe agora pode conversar em tempo real.

   <p align="center"><img src="https://github.com/user-attachments/assets/83803ac2-fbce-4d93-aae3-85eb85a3053a" alt="Chat em Tempo Real" /></p>

5. Adicione comentários para marcar colegas de equipe.

   <p align="center"><img src="https://github.com/user-attachments/assets/3b04477d-8f42-4baa-be95-867c1eaeba87" alt="Comentários em Tempo Real" /></p>

## Funcionalidades Principais

| Funcionalidade | Descrição |
|----------------|-----------|
| Alternativa OSS | Substituto direto do NotebookLM, Perplexity e Glean com colaboração em equipe em tempo real |
| 50+ Formatos de Arquivo | Faça upload de documentos, imagens, vídeos via LlamaCloud, Unstructured ou Docling (local) |
| Busca Híbrida | Semântica + Texto completo com Índices Hierárquicos e Reciprocal Rank Fusion |
| Respostas com Citações | Converse com sua base de conhecimento e obtenha respostas citadas no estilo Perplexity |
| Arquitetura de Agentes Profundos | Alimentado por [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) com planejamento, subagentes e acesso ao sistema de arquivos |
| Suporte Universal de LLM | 100+ LLMs, 6000+ modelos de embeddings, todos os principais rerankers via OpenAI spec e LiteLLM |
| Privacidade em Primeiro Lugar | Suporte completo a LLM local (vLLM, Ollama) seus dados ficam com você |
| Colaboração em Equipe | RBAC com papéis de Proprietário / Admin / Editor / Visualizador, chat em tempo real e threads de comentários |
| Geração de Vídeos | Gera vídeos com narração e visuais |
| Geração de Apresentações | Cria apresentações editáveis baseadas em slides |
| Geração de Podcasts | Podcast de 3 min em menos de 20 segundos; múltiplos provedores TTS (OpenAI, Azure, Kokoro) |
| Extensão de Navegador | Extensão multi-navegador para salvar qualquer página web, incluindo páginas protegidas por autenticação |
| 27+ Conectores | Mecanismos de busca, Google Drive, OneDrive, Dropbox, Slack, Teams, Jira, Notion, GitHub, Discord e [mais](#fontes-externas) |
| Auto-Hospedável | Código aberto, Docker em um único comando ou Docker Compose completo para produção |

<details>
<summary><b>Lista completa de Fontes Externas</b></summary>
<a id="fontes-externas"></a>

Mecanismos de Busca (Tavily, LinkUp) · SearxNG · Google Drive · OneDrive · Dropbox · Slack · Microsoft Teams · Linear · Jira · ClickUp · Confluence · BookStack · Notion · Gmail · Vídeos do YouTube · GitHub · Discord · Airtable · Google Calendar · Luma · Circleback · Elasticsearch · Obsidian, e mais por vir.

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
