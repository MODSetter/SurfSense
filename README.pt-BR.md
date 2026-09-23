<!--
  O aviso de encerramento tem prazo. Remova-o em 18 de outubro de 2026, quando a
  janela de exportação fechar, junto com o link "Importando do app hospedado"
  mais abaixo. Este arquivo acompanha o README.md seção por seção; qualquer
  mudança feita lá precisa ser refletida aqui.
  Justificativa desta página: plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Forks](https://img.shields.io/github/forks/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/network/members)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img width="128" height="128" alt="SurfSense, a alternativa open source ao NotebookLM, isolada da rede" src="surfsense_web/public/homepage/icon.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>A alternativa open source ao NotebookLM, isolada da rede.</b>
    <br />
    Transforme documentos que você não pode enviar para a nuvem em briefings, apresentações, relatórios, guias de estudo e podcasts, tudo na sua própria máquina.
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>Baixar</b></a> ·
    <a href="https://www.surfsense.com/docs">Documentação</a> ·
    <a href="#o-que-o-surfsense-cria">O que ele cria</a> ·
    <a href="#como-o-surfsense-se-compara">Comparativo</a> ·
    <a href="https://www.surfsense.com/pricing">Preços</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | Português | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

<p align="center">
  <img src="surfsense_web/public/homepage/offline-studio.png" alt="O aplicativo desktop SurfSense com o Studio aberto e o Qwen selecionado, transformando fontes locais em artefatos" />
</p>

O SurfSense é um aplicativo de desktop gratuito e open source para os documentos que você já tem. Arraste-os para dentro, faça perguntas e receba respostas que citam as fontes; depois transforme os mesmos documentos em um briefing, uma apresentação de slides, um relatório, um guia de estudo ou um podcast. Tudo roda na sua própria máquina: o índice fica no seu disco, você escolhe o modelo e o aplicativo não envia nada para fora. Não há conta para criar.

**Comece agora.** Baixe o instalador para a sua máquina e depois use a sua própria chave de modelo ou deixe o aplicativo baixar um modelo local para você.

| Plataforma | Download |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-Setup.exe) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-arm64.dmg) |
| **Linux** x64 (AppImage) | [SurfSense.AppImage](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.AppImage) |
| **Linux** x64 (deb) | [SurfSense.deb](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.deb) |

Todo link é um permalink para a versão mais recente. Você também pode escolher em [surfsense.com/downloads](https://www.surfsense.com/downloads) ou ver [todas as versões](https://github.com/MODSetter/SurfSense/releases). O AppImage se atualiza sozinho; o deb não.

> [!NOTE]
> **Usava o app web hospedado?** Ele está sendo desativado. Abra-o uma última vez para exportar seus workspaces e importe o pacote no aplicativo de desktop; documentos, pastas, títulos e conversas do chat vêm junto. A janela de exportação fecha em 18 de outubro de 2026. Detalhes na [página de encerramento](https://www.surfsense.com/sunset).

## O que o SurfSense cria

Escolha alguns documentos e um formato. O aplicativo escreve o resultado a partir das fontes que você selecionou, na sua máquina.

| Formato | O que você recebe | Precisa de |
|---|---|---|
| **Resumo** | Um panorama estruturado das fontes selecionadas | modelo de geração |
| **Flashcards** | Um baralho interativo, um cartão por vez | modelo de geração |
| **Quiz** | Perguntas de múltipla escolha com respostas | modelo de geração |
| **Mapa mental** | Um Markmap com zoom e nós recolhíveis | modelo de geração |
| **Slides** | Um `.pptx` editável, não uma imagem de apresentação | modelo de geração |
| **Documento** | Um relatório `.docx` editável | modelo de geração |
| **Planilha** | Um `.xlsx` com as tabelas extraídas das fontes | modelo de geração |
| **Página web** | Uma página HTML autocontida | modelo de geração |
| **PDF** | Um PDF já diagramado | modelo de geração |
| **Podcast** | Uma conversa em áudio com dois apresentadores, narrada offline pelo Kokoro-82M | modelo de geração + voz incluída |
| **Imagem** | Uma ilustração para o material | modelo de imagem + modelo de geração |
| **Infográfico** | Um resumo visual em um único painel | modelo de imagem + modelo de geração |

Alguns trabalhos pedem mais de um. Um guia de estudo é um resumo, um baralho de flashcards e um quiz sobre o mesmo conjunto de fontes, e um briefing para cliente costuma ser a apresentação que você mostra mais o resumo que você envia depois. Resumos em vídeo ainda não foram implementados.

## Tudo fica na sua máquina

As pessoas usam isso com autos de processo, papéis de trabalho de clientes, transcrições de entrevistas, especificações internas, pesquisas não publicadas e um semestre inteiro de anotações de aula. Você pode fazer perguntas sobre tudo isso, e cada resposta cita a fonte de onde veio. O aplicativo não envia nada disso para fora.

- **O índice é local.** A leitura dos documentos, a divisão em trechos e a geração de embeddings acontecem no seu computador, gravando em SQLite dentro de `~/.surfsense`. O SurfSense não guarda nenhuma cópia disso nem registro do que você perguntou.
- **Toda função pode rodar localmente.** O leitor de documentos, o modelo de recuperação e a voz do podcast vêm dentro do instalador. O chat e a geração de imagens vêm como servidores locais cujos pesos você baixa uma única vez, então você produz texto, áudio e imagens sem conta e sem chave de API. Nós testamos isso indexando um PDF com a rede desligada.
- **As conexões de saída vêm desligadas.** Um painel de saída lista todos os destinos que o aplicativo pode alcançar, e você liga só os que quiser.
- **Sem telemetria, sem relatório de falhas.** Nada se comunica com os nossos servidores, então não há nada para desativar nas configurações.

O SurfSense não tem como dizer se isso atende a uma norma específica. Isso depende dos seus próprios controles e do seu órgão regulador. Tudo o que o aplicativo pode dizer é em qual máquina os seus documentos estão.

## Como o SurfSense se compara

Três tipos de produto são chamados de "o NotebookLM local", e cada um responde a uma pergunta diferente. Nenhum deles é uma ferramenta ruim; eles só entregam coisas diferentes no fim.

**vs Jan, AnythingLLM, Open WebUI, LM Studio.** Eles rodam um modelo localmente e te dão um lugar para conversar com ele. O SurfSense responde à pergunta seguinte: como você tira daí um documento pronto? Use os dois juntos, se quiser, apontando o SurfSense para qualquer endpoint compatível com a OpenAI, inclusive um deles.

**vs RemNote, Quizlet, NoteGPT, StudyFetch, Gamma.** Esses realmente produzem artefatos, e alguns ficam mais bonitos que os nossos. A troca é o destino do seu material: você faz upload, paga por mês e seus arquivos ficam na conta de outra pessoa.

**vs Google NotebookLM.** Ele já entrega flashcards, quizzes, mapas mentais e resumos em áudio, então os dois produzem praticamente as mesmas coisas. A diferença é de quem é a máquina que faz o trabalho e qual modelo você pode apontar para ela.

| | Google NotebookLM | SurfSense |
|---|---|---|
| Roda offline / isolado da rede | Não | **Sim** |
| Seus documentos saem da sua máquina | Sim | **Não** |
| Exige conta | Conta Google | **Nenhuma** |
| Open source | Não | **Apache-2.0** |
| Preço | Plano gratuito; Pro $19.99/mo; Ultra $249.99/mo | **O aplicativo é gratuito** |
| Modelos | Apenas Gemini | Qualquer API compatível com a OpenAI, ou uma local |
| Limites de fontes | De 50 a 600 fontes, 500.000 palavras cada | O que couber no seu disco |
| Resumos em áudio e vídeo | Sim, e melhores | Áudio sim, offline; vídeo ainda não |

O NotebookLM ganha em qualidade de áudio e tem vídeo. Se você não se incomoda que as suas fontes fiquem nos servidores do Google, use-o. Se você se incomoda, aqui está o mesmo tipo de ferramenta sem o upload.

## Início rápido

Você não precisa de Docker, terminal, GPU nem arquivo compose.

1. **Baixe o instalador** na tabela acima. Ele é assinado, então o seu sistema operacional não vai reclamar.
2. **Escolha um modelo.** Deixe o aplicativo baixar um modelo local (Qwen3 em seis tamanhos, a partir de 0,5 GB) ou cole a URL base e a chave de qualquer API compatível com a OpenAI. O seletor confere se a sua máquina consegue rodar o modelo antes de oferecê-lo, e toda chave que você informa fica armazenada de forma criptografada, com o segredo guardado no keychain do seu sistema operacional.
3. **Solte seus documentos.** O aplicativo processa PDFs, arquivos do Office e imagens na sua máquina.
4. **Faça perguntas.** Cada resposta cita a fonte de onde veio.
5. **Abra o Studio,** escolha um formato e pegue o arquivo.

O download é a parte lenta, porque o instalador carrega o leitor de documentos, o modelo de recuperação, a voz do podcast e os servidores de modelos locais, e é isso que faz o aplicativo funcionar com a rede desligada.

## Documentação e comunidade

O aplicativo e suas atualizações são gratuitos. Uma licença adiciona plugins e suporte prioritário e não bloqueia mais nada, então uma licença expirada ainda deixa com você o aplicativo e todas as atualizações futuras. Veja os [preços](https://www.surfsense.com/pricing).

A stack Docker deste repositório (`surfsense_backend`, `surfsense_web`, arquivos compose) continua open source e instalável, e tem **suporte da comunidade: sem SLA e sem serviço hospedado por trás.** O aplicativo de desktop é o caminho com suporte para novos usuários.

- [Documentação](https://www.surfsense.com/docs) sobre instalação, modelos, formatos do Studio e auto-hospedagem
- [Importando do app hospedado](https://www.surfsense.com/sunset)
- [Servidor MCP](./surfsense_mcp) para a API de scraping hospedada
- [Discord](https://discord.gg/ejRNvftDp9) para ajuda e ideias, [Discussions](https://github.com/MODSetter/SurfSense/discussions) para a direção do produto, [Issues](https://github.com/MODSetter/SurfSense/issues) para bugs reproduzíveis
- **Dê uma estrela no repositório** se quiser acompanhar para onde isso vai

## Como contribuir

Pull requests são bem-vindos, e o [CONTRIBUTING.md](CONTRIBUTING.md) explica todo o fluxo. Em resumo:

- **Encontre algo para fazer:** uma issue com o rótulo [`good first issue`](https://github.com/MODSetter/SurfSense/labels/good%20first%20issue) ou [`help wanted`](https://github.com/MODSetter/SurfSense/labels/help%20wanted), ou uma linha da lista Known gaps (lacunas conhecidas) no fim de cada documento em [`docs/architecture/`](docs/architecture/overview.md).
- **Leia antes como funciona:** [`docs/`](docs/README.md) explica cada funcionalidade e por que ela é feita assim, e o [`docs/ROADMAP.md`](docs/ROADMAP.md) mostra no que os mantenedores estão trabalhando.
- **Abra um PR para `dev`.** Correções de bugs e documentação não precisam de discussão antes; uma funcionalidade nova começa com uma proposta de design curta. O aplicativo de desktop fica em [`surfsense_local/`](./surfsense_local) e o README dele cobre o ciclo de desenvolvimento.

Obrigado a todos os nossos Surfers:

<p align="center">
  <a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="Pessoas que contribuem com o SurfSense" />
  </a>
</p>

## Histórico de estrelas

<p align="center">
  <a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
    </picture>
  </a>
</p>

## Licença

Apache-2.0. Veja o arquivo [LICENSE](LICENSE).
