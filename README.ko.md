<!--
  서비스 종료 안내에는 기한이 있습니다. 2026년 10월 18일에 README.md의 같은 안내와 함께 삭제하세요.
  이 파일은 README.md와 절마다 대응합니다.
  근거: plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img alt="SurfSense, 네트워크와 분리해 쓰는 오픈소스 NotebookLM 대안" src="www/public/homepage/banner.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>네트워크와 분리해 쓰는 오픈소스 NotebookLM 대안.</b>
    <br />
    내 컴퓨터에서 문서를 조사하고, 변환하고, 편집하는 AI 에이전트.
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>다운로드</b></a> ·
    <a href="#형식별로-하는-일">형식</a> ·
    <a href="#빠른-시작">빠른 시작</a> ·
    <a href="#비교">비교</a> ·
    <a href="#플러그인">플러그인</a> ·
    <a href="https://www.surfsense.com/pricing">요금</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | 한국어 | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

**추적된 변경과 메모로 계약서를 레드라인 처리합니다**

https://github.com/user-attachments/assets/88326b9d-e763-46db-9635-75f9df9e8682

**웹에서 소스를 추가하고 웹 페이지로 만듭니다**

https://github.com/user-attachments/assets/073577b7-f055-4f59-8540-330bd764aeb0

SurfSense는 업로드할 수 없는 문서를 위한 무료 오픈소스 데스크톱 앱입니다. 프라이버시를 중시하는 NotebookLM 스타일의 AI 에이전트로, 내 컴퓨터에서 문서를 조사하고, 변환하고, 편집합니다. 색인은 내 디스크에 남고, 모델은 로컬이든 원격이든 내가 고르며, 만들 계정도 없습니다.

| 플랫폼 | 다운로드 |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://www.surfsense.com/downloads/windows?src=readme) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://www.surfsense.com/downloads/mac?src=readme) |
| **Linux** x64 | [AppImage](https://www.surfsense.com/downloads/linux-appimage?src=readme) · [deb](https://www.surfsense.com/downloads/linux-deb?src=readme) |

## 빠른 시작

1. SurfSense를 설치하고 초기 설정을 마칩니다.
2. 파일이나 폴더를 소스에 끌어다 놓습니다.
3. 에이전트에게 파일 검색, 내용 추출, 편집을 요청합니다.

## 형식별로 하는 일

| 형식 | 조사(출처를 밝힌 답변) | 만들기 | 편집(사본으로) | 변환 |
|---|---|---|---|---|
| **PDF** | ✓ 스캔한 페이지도³ | ✓ | 양식 채우기와 평면화, 워터마크·페이지 번호·머리글·바닥글 넣기 | 페이지 병합, 분할, 추출, 회전, 순서 변경 |
| **Word** `.docx` | ✓ | ✓ 또는 내 `.docx`를 템플릿으로 | ✓ 본문 텍스트, 추적된 변경과 메모 형태로 | PDF로¹ |
| **Excel** `.xlsx` | ✓ 에이전트가 수식도 읽음 | ✓ 수식과 네이티브 차트 포함 | ✓ 셀 값과 수식 | pandas로 분석하고 결과를 차트로 |
| **PowerPoint** `.pptx` | ✓ | ✓ 또는 내 `.pptx`를 템플릿으로 | 슬라이드와 노트의 텍스트 바꾸기, 슬라이드 삭제·복제 | PDF로¹ |
| **CSV** | ✓ | — | — | pandas로 분석하고 결과를 차트로 |
| **이미지** PNG, JPEG, TIFF, BMP, WebP | ✓ OCR로 텍스트 인식³ | 이미지와 인포그래픽² | — | 새 문서에 넣기 |
| **Markdown**, 일반 텍스트 | ✓ | ✓ Markdown | — | — |
| **HTML** | ✓ | ✓ 웹 페이지 | — | — |
| **녹음 파일** WAV, MP3, FLAC, Ogg Vorbis | ✓ 내 컴퓨터에서 텍스트로 변환 | — | — | — |
| **팟캐스트** (오디오) | — | ✓ 스크립트 포함, 기본적으로 내 컴퓨터에서 음성 생성 | — | — |
| **마인드맵, 플래시카드, 퀴즈** | — | ✓ 앱 안에서 | — | — |

<sub>¹ 설정에서 켜는 Office 지원(LibreOffice)이 있어야 합니다. 설치 파일에는 절대 들어 있지 않습니다. ² 로컬이든 원격이든 이미지 모델이 필요하며, 기본으로 선택된 모델은 없습니다. ³ OCR은 라틴 문자, 중국어 문자, 일본어 문자를 읽습니다.</sub>

편집, 변환, PDF 도구는 항상 새 파일을 만들며, 원본은 절대 바뀌지 않습니다. 지금은 PDF, Word, Excel에서 할 수 있는 일이 가장 많고, 다른 형식의 지원도 계속 나아지고 있습니다.


## 플러그인

**설정 › 플러그인**에서 연결하세요.

**SurfSense 제공.** 내 계정 없이 공개 페이지를 읽으며, SurfSense 라이선스가 필요합니다. [앱을 다운로드](https://www.surfsense.com/downloads)한 다음 앱에서 이메일을 입력하면 14일 무료 라이선스를 받을 수 있습니다.

| 플러그인 | 하는 일 |
|---|---|
| **Google Search** | Google에서 검색하고 검색 결과, 광고, 관련 질문 읽기 |
| **Web Crawl** | 웹 페이지를 읽거나 사이트 전체를 크롤링해 깔끔한 텍스트로 만들기 |
| **YouTube** | YouTube 동영상, 채널, 댓글 읽기 |
| **TikTok** | TikTok 동영상과 댓글 읽기, 사용자 검색, 지금 인기 있는 콘텐츠 보기 |
| **Reddit** | Reddit 공개 게시물과 댓글 스레드, 또는 커뮤니티 전체 읽기 |
| **Instagram** | Instagram 공개 프로필, 게시물, 릴스 읽기, 프로필 검색 |
| **Google Maps** | Google Maps에서 장소를 찾고 리뷰 읽기 |
| **Amazon** | Amazon 상품과 검색 결과 읽기 |
| **Walmart** | Walmart 상품, 검색 결과, 리뷰 읽기 |
| **Indeed** | Indeed의 채용 공고 읽기 |

**서드파티.** [플러그인 레지스트리](backend/plugins/registry)에 있는 DeepWiki, Notion 같은 MCP 서버 또는 URL로 직접 추가한 서버입니다. 라이선스는 필요 없으며, 허용하기 전까지 꺼져 있습니다.

## 비교

| | NotebookLM (현재 Gemini Notebook) | SurfSense |
|---|---|---|
| 오프라인 / 네트워크 분리 환경에서 동작 | 아니요 | **예** |
| 문서가 내 컴퓨터를 떠남 | 예 | **아니요**, 원격 모델을 고르지 않는 한 |
| 내 파일을 편집할 수 있음 | 아니요 | **예** |
| 오픈소스 | 아니요 | **Apache-2.0** |
| 모델 | Gemini만 | 모든 OpenAI 호환 API 또는 로컬 모델 |

## 커뮤니티

- 도움은 [Discord](https://discord.gg/ejRNvftDp9), 버그는 [Issues](https://github.com/MODSetter/SurfSense/issues), 아이디어는 [Discussions](https://github.com/MODSetter/SurfSense/discussions).
- **기여:** PR은 `dev` 브랜치를 대상으로 엽니다. 개발 루프는 [CONTRIBUTING.md](CONTRIBUTING.md)와 [`surfsense_local/`](./surfsense_local)에서 확인하세요. 동작 방식은 [`docs/`](docs/README.md)에 있습니다.

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors"><img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="SurfSense 기여자" /></a>

## 라이선스

Apache-2.0. [LICENSE](LICENSE)를 보세요.
