# Global demand: 26 markets, 15 languages

The world outside the US, measured with the same list, the same source and the
same day as [`01-keyword-research.md`](01-keyword-research.md). DataForSEO
`keyword_overview`, pulled 14 Sep 2026, Google desktop. 27 pulls (26 markets;
Canada in English and in French) of one shared English list plus a translated
list per language, so every market is comparable with every other one. Raw
archives, the keyword lists and the pivot are in
[`data/intl/`](data/intl/); [`data/README.md`](data/README.md#international-pulls)
says how to re-run it.

Three reading rules apply to every number below.

- Volumes are `recent`: the median of the last three months, capped at the
  12-month figure. The US privacy cluster jumped 5-25x in July-August 2026 and
  the 12-month average lies in both directions; `recent` is the level a page
  launched this quarter would meet. Where a term is still climbing, the text
  gives the last three months as well.
- Close variants Google Ads folds together (`ローカルllm` / `ローカル llm`,
  `self hosted llm` / `self-hosted llm`) are counted once. The pivot lists
  them with a `variant_of` column.
- "Addressable" is everything except the NotebookLM brand head (`notebooklm`,
  `노트북lm`), its how-to long tail (`使い方`, `教學`, `사용법`), the
  in-my-language queries (`notebooklm em português`) and competitor tool names
  (`ollama`, `lm studio`), none of which a landing page converts. A dash or
  "below threshold" means DataForSEO returned no row, which happens under
  roughly ten searches a month. Google Ads reports volume in fixed buckets
  (…49,500, 60,500, 74,000, 90,500, 110,000…), so identical figures in two
  markets are a coincidence of rounding, not shared data.

## The one-table version

| market | lang | addressable /mo | value index $/mo | English share | NotebookLM brand /mo | what leads |
|---|---|---|---|---|---|---|
| **United States** | en | **93,940** | **1,296,977** | 100% | 673,000 | local llm 8,100 · open source ai 6,600 · private ai chatbot 5,400 |
| **Japan** | ja | **57,800** | **137,355** | 10% | 673,000 | ローカルLLM 22,200 · NotebookLM 料金 8,100 · ローカルAI 5,400 |
| **India** | en | **28,930** | 27,039 | 100% | **1,500,000** | open source ai 2,900 · notebooklm app 2,900 · notebooklm download 2,400 |
| **Germany** | de | **16,800** | 72,649 | 61% | 301,000 | open source KI 1,300 · local llm 1,000 · local ai 1,000 |
| United Kingdom | en | 11,830 | 87,405 | 100% | 110,000 | sovereign ai 2,400 · open source ai 1,000 · obsidian ai 880 |
| South Korea | ko | 11,150 | 26,198 | 22% | 503,000 | 소버린 AI 6,600 · local llm 720 · 오픈소스 AI 480 |
| France | fr | 9,900 | 34,633 | 40% | 301,000 | notebooklm gratuit 1,900 · IA open source 880 · local ai 720 |
| Brazil | pt | 9,540 | 15,940 | 57% | **1,220,000** | notebooklm download 1,000 · obsidian ai 720 · notebooklm app 720 |
| Canada | en | 7,470 | 63,534 | 100% | 110,000 | local llm 880 · open source ai 720 · obsidian ai 590 |
| Spain | es | 6,180 | 18,972 | 48% | 823,000 | notebooklm gratis 880 · notebooklm app 880 · IA para abogados 390 |
| Australia | en | 5,890 | 46,496 | 100% | 74,000 | open source ai 590 · local llm 590 · sovereign ai 480 |
| Mexico | es | 5,690 | 6,770 | 23% | 368,000 | notebooklm gratis 2,900 · IA para abogados 390 · notebooklm app 320 |
| Italy | it | 5,210 | 14,880 | 65% | 550,000 | AI open source 720 · notebooklm app 590 · notebooklm download 390 |
| Indonesia | en | 4,280 | 6,393 | 100% | 550,000 | open source ai 720 · obsidian ai 720 · ai research assistant 590 |
| Taiwan | zh-TW | 3,690 | 6,594 | 37% | 450,000 | NotebookLM 下載 1,900 · notebooklm app 480 · AI 資安 260 |
| Netherlands | nl | 3,600 | 18,536 | 92% | 110,000 | local llm 390 · local ai 390 · open source ai 320 |
| Philippines | en | 2,810 | 3,012 | 100% | 165,000 | ai research assistant 590 · notebooklm app 480 · is notebooklm free 390 |
| Poland | pl | 2,120 | 5,854 | 45% | 49,500 | AI dla prawników 590 · local llm 390 · AI open source 320 |
| Singapore | en | 2,010 | 7,201 | 100% | 90,500 | obsidian ai 320 · sovereign ai 260 · notebooklm app 210 |
| South Africa | en | 1,980 | 2,914 | 100% | 74,000 | notebooklm app 320 · open source ai 260 · notebooklm download 210 |
| Sweden | sv | 1,630 | 3,957 | 90% | 27,100 | local llm 260 · open source ai 170 · local ai 170 |
| Switzerland | de | 1,170 | 3,696 | 86% | 60,500 | notebooklm app 210 · open source ai 170 · local llm 170 |
| UAE | en | 760 | 2,083 | 100% | 49,500 | open source ai 110 · obsidian ai 110 · notebooklm download 70 |
| Austria | de | 760 | 2,615 | 67% | 22,200 | open source KI 110 · notebooklm app 110 · open source ai 90 |
| New Zealand | en | 700 | 1,580 | 100% | 18,100 | open source ai 110 · obsidian ai 90 · local llm 90 |
| Ireland | en | 460 | 1,110 | 100% | 9,900 | open source ai 90 · ai podcast generator 90 · obsidian ai 70 |

Value index is `Σ recent × CPC`: what the same clicks would cost in Google
Ads, a proxy for what buyers are worth in a market, not a revenue forecast.
The Canada-French pull (7,340 addressable, 98% of it the English rows already
counted under Canada) is archived but excluded from every total here.

## Nine findings

**1. The US is a third of the searches and two thirds of the money.** 93,940
of 296,300 addressable searches a month (32%) and $1.30M of $1.91M in value
index (68%). By region: Asia 111,000 (38%), Europe 60,000 (20%), the
English-speaking countries outside the US 28,000 (10%), Spanish and
Portuguese 21,000 (7%). Median CPC is $7.63 in the US against $2.44 in Japan,
$1.29 in Brazil and $0.78 in India. Everything in
[`02-page-briefs.md`](02-page-briefs.md) targets the US, and this pass
confirms that is where the licence revenue is.

**2. Japan is the second market by both measures, on one term, and nobody is
competing for it.** 57,800 addressable searches and a $137K value index, 20%
of global demand. `ローカルLLM` ("local LLM") reports 22,200 a month and ran
at **40,500, 40,500, 33,100** over June-August, up 174% year on year, at
**KD 0** and $1.98. `ローカルAI` adds 5,400 (+326%, KD 0). `NotebookLM 料金`
(pricing) is 8,100 at KD 3, `無料` (free) 1,900, `アプリ` (app) 2,900,
`ダウンロード` (download) 1,000 (+319%), and the how-to query `使い方` is
27,100. Only 10% of Japanese demand is in English. Japan's NotebookLM
audience is the same size as America's (673,000), and it is **not looking for
an alternative**: `代替`, `代わり` and `類似` (alternative, substitute,
similar) are all below threshold. The Japanese page is a local-LLM page that
happens to be a NotebookLM, not the other way round. See the tiers.

**3. Two words travel; the rest do not.** Addressable demand by concept,
outside the US:

| concept | outside US | markets with volume | US, for comparison |
|---|---|---|---|
| local (llm / ai) | **51,700** | 21 | 16,430 |
| notebooklm pricing / free | 28,270 | 25 | 4,290 |
| notebooklm download / app | 27,330 | 25 | 4,250 |
| open source | 21,210 | 25 | 9,520 |
| sovereign | 17,160 | 9 | 3,600 |
| PKM / Obsidian | 11,580 | 24 | 4,990 |
| RAG and chat-with-docs | 7,700 | 25 | 2,010 |
| podcast / audio overview | 6,890 | 25 | 3,300 |
| notebooklm in my language | 6,400 | 14 | 0 |
| private | 5,420 | 16 | 15,600 |
| offline | 4,750 | 20 | 1,780 |
| legal vertical | 4,180 | 21 | 2,510 |
| compliance (local law) | 4,150 | 18 | 11,640 |
| research / academic | 3,210 | 20 | 1,600 |
| notebooklm switching / vs | 2,930 | 20 | 940 |
| notebooklm alternative | 2,160 | 17 | 970 |
| self-hosted | 1,340 | 9 | 5,330 |
| notebooklm privacy | 1,220 | 14 | 160 |
| on-prem | 1,080 | 11 | 3,120 |
| air-gap | **80** | 6 | 1,900 |

"Local" and "open source" exist in every language with real volume:
`ローカルLLM` 22,200, `lokale KI` 720 (+400%), `IA locale` 590 (+243%),
`IA local` 320 in Spain and 390 in Brazil (+414%), `open source KI` 1,300,
`IA open source` 880 in France and 590 in Brazil, `AI open source` 720 in
Italy, and English `local llm` in 20 markets and `open source ai` in 25.
"Private" is a US word: 74% of its global volume is American, and `KI
privat`, `IA privée` (50), `プライベートAI`, `프라이빗 AI` are below threshold
or near it. "Self-hosted" barely exists outside English: `KI selbst hosten`
140, everything else (`IA auto-hébergée`, `IA autoalojada`, `セルフホスト`,
`자체 호스팅`, `självhostad`) below threshold. "Air-gapped" is 80 searches a
month across the other 25 markets combined. **Outside the US the H1 is
"local, open-source NotebookLM"; "air-gapped", "private" and "self-hosted"
are US enterprise qualifiers and second-paragraph words everywhere else.**

**4. The summer 2026 surge is a US event.** *US v. Heppner* and the OpenAI
logs order (`01`, historical section) pushed US `local llm` to 74,000 and
`private ai` to 60,500 in August 2026. The same months abroad: `local llm` UK
1,600 → 1,000 → 1,000, Germany 1,600 → 1,300 → 1,000, India 1,600 → 2,400 →
2,400; `private ai` UK 390, 390, 390 and India 880, 880, 880. `소버린 AI` fell
55% year on year in Korea. International demand is structural, growing
100-400% a year on the local-AI terms, and not news-driven. US pages should
be built for the level after the spike decays; international pages can be
planned on trend.

**5. NotebookLM's users are in Asia and Latin America, they want it free,
installed and in their language, and they are not looking for an
alternative.** Brand head searches: India 1.50M a month (1.83M over the last
three), Brazil 1.22M, Spain 823K, Japan 673K, the US 673K, Italy 550K,
Indonesia 550K, Korea 503K, Taiwan 450K. The three brand intents we can
convert are all bigger outside the US than inside it: pricing/free 28,270
(`notebooklm gratis` Mexico 2,900 and Spain 880, `gratuit` France 1,900 at
KD 7, `料金` Japan 8,100, `is notebooklm free` India 2,400), download/app
27,330 (`notebooklm app` in 26 of 26 markets, India 2,900; `notebooklm
download` India 2,400 running at 4,400-5,400 and +400%, Brazil 1,000 +519%,
`下載` Taiwan 1,900, `ダウンロード` Japan 1,000), and in-my-language 6,400
(`em português` 1,300, `en español` 1,000 + 590 + 320, `in italiano` 880 +
170, `中文` 880, `en français` 390). Against that, `notebooklm alternative`
in the singular has volume in **seven** markets and the whole alternative
concept is 2,160 a month outside the US, with Germany (390) the only
non-English market above 150. **Download/app and the free/pricing question
are the two brand intents with demand in every market pulled**, and the app's own
language switcher is an SEO asset: `notebooklm em português` is a request for
a Portuguese interface, which a desktop app can answer and Google cannot.

**6. Legal is the universal vertical.** The lawyer query has volume in 21 of
25 non-US markets: Poland's single biggest addressable term is `AI dla
prawników` (590, KD 3, +177%); `IA para abogados` is 390 in Spain ($5.29) and
390 in Mexico; `KI für Anwälte` 320 at $12.25 and KD 0; `ai for lawyers` UK
320 at $18.36, Australia 210 at $18.03, Canada 170 at **$39.71**, India 720;
`IA per avvocati` 210 at $7.66; `IA pour avocats` 90 at $8.84; `AI voor
advocaten` 50 at $15.25; `AI för jurister` 50. One legal page in English,
with German and Spanish versions, covers the highest-CPC vertical this
product has in every market.

**7. Compliance vocabulary is the local statute, and it carries budget.**
`DSGVO konforme KI` 260 at $11.79 (+255%), `datenschutzkonforme KI` 170,
`DSGVO KI` 170, `KI Datenschutz` 480 at $7.01; `IA RGPD` 140 at $7.23 and
`RGPD IA` 110 at $10.30; `LGPD IA` 90 in Brazil; `AVG AI` 20 at $14.56 in the
Netherlands; `AI 資安` 260 in Taiwan; `生成AI 情報漏洩` (generative-AI data
leakage) 480 and `生成AI セキュリティ` 320 at $7.12 in Japan; `생성형 AI 보안`
50 in Korea. HIPAA is a US term (`hipaa compliant ai` 4,400 US at $46.33, 40
in Canada, 20 in India, nowhere else), and `gdpr compliant ai` in English is
a US search too (3,600 US, 20 UK). Every localised page gets one section
named for the local law, not for "compliance".

**8. Sovereign AI is a policy term, not a buyer.** 17,160 a month outside the
US, but 7,080 of it is Korea (`소버린 AI` 6,600 at **$0.00 CPC**, down 55%,
14,800 → 8,100 → 5,400), 5,790 Japan (`ソブリンAI` 5,400, $2.68), 2,400 the UK
(`sovereign ai`, $13.28, KD 22, +140%), then Australia and Canada 480 each,
`IA souveraine` 480 in France. `Souveräne KI` is below threshold in Germany
despite the EU discourse, as are `IA soberana`, `suverän AI`, `soevereine AI`
and `suwerenna AI`. The UK is the only market where the term carries
commercial CPC. Do not build a "sovereign AI" page; get SurfSense named in
the policy coverage that ranks for it (`05-serp-landscape.md`, third-party
citations) and use the phrase in UK and Australian enterprise copy.

**9. The below-threshold list is as useful as the volume list.** Requested in
the local language and absent: German `souveräne KI`, `KI ohne Internet`,
`self hosted KI`, `KI on premise`, `air gapped KI`, `KI für Kanzleien`;
French `alternative à NotebookLM`, `IA auto-hébergée`, `IA sans internet`,
`IA on premise`, `IA sur site`; Spanish `alternativa a NotebookLM`, `IA
autoalojada`, `IA confidencial`, `IA segura`, `ejecutar LLM localmente`, and
in Mexico even `IA local`; Portuguese `alternativa ao NotebookLM`, `IA sem
internet`, `IA soberana`, `IA auto hospedada`, `IA on premise`; Japanese
`NotebookLM 代替`, `セルフホスト LLM`, `エアギャップ AI`, `プライベートAI`, `セキュア
AI`; Korean `NotebookLM 대안`, `로컬 LLM`, `로컬 AI`, `프라이빗 AI`, `셀프호스팅
AI`, `에어갭 AI`; Traditional Chinese every category term tried (`本地 LLM`,
`地端 AI`, `離線 AI`, `私有 AI`, `開源 AI`, `地端部署 AI`); Italian `AI
locale`, `IA privata`, `IA sovrana`, `IA on premise`; Dutch `lokale LLM`,
`zelf gehoste AI`, `soevereine AI`; Polish `lokalna AI`, `prywatna AI`,
`suwerenna AI`; Swedish `privat AI`, `självhostad AI`, `GDPR AI`. Two lessons.
The negation and self-hosting framings ("without internet", "self-hosted",
"air-gapped") are how vendors talk, in every language; buyers type "local".
And in Korea, Taiwan and Switzerland the technical vocabulary is English
(`local llm` 720 in Korea, `로컬 LLM` absent; `ollama` 33,100 in Taiwan,
`本地 LLM` absent), so a translated category page there would rank for
nothing. **Use the glossary term with volume; where there is none, use the
English term.**

## Tiers: what to build, in order

| tier | markets | what | why |
|---|---|---|---|
| **1. Build** | US (serves every English market) | all pages in `02` | 68% of value; every concept has volume |
| **2. Localise** | Japan | `/ja/`: home written as a `ローカルLLM` page, downloads, `料金`/`無料` pricing, a `使い方` quickstart, a `情報漏洩`/`セキュリティ` section; Studio: a slides page (`スライド作成 AI`) and a summary page (`要約 AI`) | #2 market, KD 0 on a 22K term running at 33-40K, 10% English share, no competitor present, no "alternative" intent to fight over; 29K more in slides and summary at KD 1-15 |
| **2. Localise** | Germany (+ Austria, Switzerland via hreflang) | `/de/`: home (`lokale KI` / `open source KI`), downloads, `kostenlos`/`Preis` pricing, one DSGVO section, `KI für Anwälte`; Studio: a slides page (`Präsentation erstellen KI`) and a `Lernzettel` study page | 16,800 addressable, $73K value, 39% in German at KD 0-5, `lokale KI` +400%, the largest alternative demand of any non-English market (390; only the US and India are higher); 9,400 in slides at KD 5-11 |
| **3. Translate three pages** | France, Spain + Mexico, Brazil | `/fr/`, `/es/`, `/pt-br/`: home, downloads, free/pricing FAQ | 60-85% of their addressable demand is brand-free, brand-download and in-my-language; `gratuit` 1,900 KD 7, `gratis` 3,780 across ES + MX, `download` + `baixar` 1,320 in Brazil |
| **4. English + hreflang** | UK, Canada, Australia, India, Ireland, Singapore, NZ, South Africa, UAE, Philippines, Indonesia, Netherlands, Sweden, Switzerland | nothing new; `hreflang` alternates on the English pages | English share 86-100%; local terms below threshold |
| **4. English + hreflang, watch** | Korea, Taiwan, Italy, Poland, Austria | same; re-pull quarterly | KR category demand is in English and `소버린` is falling; TW is brand-only (`下載` 1,900 is the one string to localise on `/downloads`); IT is the next Tier 3 candidate (5,210, `in italiano` 1,050, `gratis` 260, `avvocati` 210); PL is one legal term |

Tier 2 is a translation and a maintenance commitment, not a mirror: docs stay
English except the Japanese quickstart, the blog is not translated, and the
downloads page renders from the release manifest so localising it is a string
file. Tier 3 is three pages per language, translated once and reviewed per
release. Tier 4 costs a `<link rel="alternate">` block.

**Order of work.** Japan first, because it is the largest gap between demand
and competition anywhere in this research and the page is a single-concept
page. Germany second, after the English legal and compliance sections exist
to translate. Tier 3 when the downloads page is stable, since that is the page
that carries those markets. None of this is a launch blocker; the US pages
ship first per `00d`.

### Checked against our own users, 17 Sep 2026 — and Brazil moves up

Production chat is **majority non-English**: 18% of thread titles and 21% of
user queries contain non-Latin script before counting Spanish, Portuguese and
French ([`07-what-users-do.md`](07-what-users-do.md)). That looks like an
argument for localising sooner, so the professional terms were re-pulled in
Spain, Mexico and Brazil to test it. **It is not**, and the US-first conclusion
above survives intact:

| market | best professional term | volume | kd | cpc |
|---|---|---|---|---|
| US (`en`) | ai for lawyers | 2400 | 30 | **55.59** |
| Spain (`es`) | ia para abogados | 390 | 15 | 5.34 |
| Mexico (`es`) | ia para abogados | 480 | **1** | 1.43 |
| Brazil (`pt`) | criar apresentação com ia | 2900 | **7** | 1.66 |

An order of magnitude less volume and a twentieth of the click value. **Users
are not searchers, and searchers are not buyers** — a global free-desktop
audience does not imply global commercial demand, and this is the cleanest
evidence in the folder for that distinction.

One change does follow. **Brazil moves to the front of Tier 3**, ahead of France
and Spain, on cost-to-win rather than market size:

| keyword | volume | trend | referring domains in top 10 |
|---|---|---|---|
| ia local | 480 | **+614%** | **1.2** |
| ia offline | 390 | **+182%** | **0.3** |
| ia para documentos | 210 | +191% | 24.7 |
| notebooklm em português | 1600 | +53% | 1,057 |

A top-10 averaging 0.3 referring domains is an empty SERP on a term growing
182% a year. That is the cheapest position in this entire research, and it costs
one translated page — `/pt-br/` was already Tier 3, so this is a reordering, not
a new commitment. Mexico and Brazil are not archived; see
[`data/README.md`](data/README.md#not-saved-here).

## Per-market notes

**United States.** Covered in `01` and `02`. The one international caveat: the
US is the only market where `private`, `self-hosted`, `on-prem`, `HIPAA` and
`air-gapped` have volume, so copy written for the US reads as jargon when
served to the UK, Canada and Australia through hreflang. Keep the H1 and first
screen on the shared vocabulary (local, open source, offline, free) and put
the US-only words in the enterprise section.

**Japan.** Local AI is a mainstream technical topic and the vocabulary is
katakana English: `ローカルLLM` 22,200 (+174%, KD 0), `ローカルAI` 5,400
(+326%, KD 0), `llm ローカル環境` 170, `ローカルRAG` 170 at $5.83, and English
`local llm` 1,900 on top. Enterprise words are `オンプレAI` / `オンプレミスAI`
210 each (+53%, +86%), `オンプレミスLLM` 90 at $12.96, `生成AI 情報漏洩` 480,
`生成AI セキュリティ` 320 at $7.12, `NotebookLM セキュリティ` 480 and `NotebookLM
情報漏洩` 320. `オフラインAI` 590 (+85%), `オープンソースAI` 590 (+126%),
`オープンソースLLM` 320, `プライベートLLM` 110. NotebookLM's Japanese audience
(673,000) asks `使い方` 27,100, `料金` 8,100, `無料` 1,900, `アプリ` 2,900,
`ダウンロード` 1,000, `enterprise` 1,000, `api` 1,300. `AnythingLLM` is 3,600
and up 408%; `Obsidian AI` 1,600. Yahoo Japan is Google-powered, so one set of
pages covers 95%+ of Japanese search. `ソブリンAI` 5,400 is policy press.
Studio: `スライド 作成 ai` 14,800 at KD 15 and `要約 ai` 5,400 at KD 1 are the
largest low-difficulty artifact terms outside the US; India's bigger ones are
converters and KD 58-73 generics ("Studio outputs abroad").

**India.** The largest NotebookLM audience on earth (1.50M brand searches,
1.83M over the last three months) and 100% English. `notebooklm app` 2,900,
`notebooklm download` 2,400 (running 4,400-5,400, +400%), `is notebooklm
free` 2,400, `notebooklm for windows` 1,000 (+156%), `notebooklm pricing`
720, `notebooklm alternatives` 480 (KD 0, the plural; the singular is below
threshold), `notebooklm for students` 590 (+700%). Category: `open source ai`
2,900, `open source llm` 1,600, `local llm` 1,300 (running 2,400, +173%),
`offline ai` 1,300 (+222%), `ai for pdf` 1,600, `ai research assistant` 1,300
(+805%), `ai for lawyers` 720 at $2.33, `obsidian ai` 1,000 (+307%). Median
CPC $0.78. India converts to installs, stars and contributors, not licences:
`/downloads` and the free answer serve it entirely, and its volume must not
pull the pricing page toward "free forever" copy. It is also the growth market
for the study hub: `best ai for studying` 4,400 (+184%), `notebooklm for
studying` 720 (+3233%), `pdf to quiz` 390 at KD 10, all in English.

**Germany, Austria, Switzerland.** Germans search the category in both
languages and the brand in English. German: `open source KI` 1,300 (KD 5,
+116%, the softest real-volume term in this research), `lokale KI` 720 (KD 0,
+400%, 880 → 1,000 → 1,300), `KI Datenschutz` 480, `KI für Anwälte` 320 at
$12.25, `lokale LLM` 320 (+179%), `lokales LLM` 210, `KI lokal betreiben` 260,
`offline KI` 260, `DSGVO konforme KI` 260 at $11.79, `Obsidian KI` 320
(+929%), `KI selbst hosten` 140; brand: `notebooklm app` 880, `download` 590
(+182%), `alternative` 320 (12-month 390, KD 0), `kostenlos` 320 (+143%),
`Preis` 210, `deutsch` 320, `mcp` 210 (+967%). English `local llm` and
`local ai` are 1,000 each. Studio demand is in German too: `Präsentation
erstellen KI` 5,400 at KD 11, `Lernzettel erstellen KI` 1,000, `Karteikarten`
1,190 across three forms, `KI zum Lernen` 880 (+86%). Austria is a twentieth of Germany with the same
shape (`open source KI` 110 +180%). Switzerland searches in English (86%):
`lokale KI` and `offline KI` are below threshold there. One `/de/` set with
`de`, `de-AT`, `de-CH` hreflang.

**United Kingdom, Ireland.** A fifth of the US on every term with the same
vocabulary, plus `sovereign ai` 2,400 at KD 22 and $13.28 (+140%), `ai for
lawyers` 320 at $18.36 (KD 6), `secure ai` 210 at $13.72, and `gdpr compliant
ai` 20 at $23.45. `obsidian ai` 880 (+400%), `local ai` 720 (+175%),
`notebooklm download` 170 (+143%), `notebooklm alternative` 110. No separate
pages; the UK is the market where "sovereign" belongs in enterprise copy, and
where students say *revision* (`flashcards for revision` 1,900 at KD 1,
`revision ai` 320): one H2 on the English flashcards page.

**South Korea.** 503K brand searches (`노트북LM` 368K +235%, `notebooklm`
135K) and how-to in Korean (`노트북LM 사용법` 1,600), but the category is
searched in English: `local llm` 720 (+83%, $5.78, KD 0) against `로컬 LLM`
below threshold; `오픈소스 AI` 480 and `오픈소스 LLM` 390 at $6.98 are the
Korean exceptions, with `온프레미스 AI` 140 (+271%) and `오프라인 AI` 170.
`소버린 AI` 6,600 is policy news at $0.00, down 55%. `notebooklm mcp` 480
(+700%). Naver holds about half of Korean search and needs a Korean site and
Naver Search Advisor registration; not worth it for 4,000 category searches.
English pages plus hreflang, re-check in a year.

**France, Canada-French.** `notebooklm gratuit` 1,900 at KD 7 (+122%) is the
third largest brand-free term anywhere; `IA open source` 880 at KD 0, `IA
locale` 590 (KD 0, +243%, steady at 720), `LLM local` 390 (KD 0), `IA en
local` 260, `IA souveraine` 480, `podcast IA` 390, `IA RGPD` 140 + `RGPD IA`
110, `IA pour avocats` 90 at $8.84, `Obsidian AI` 320 (+333%), `notebooklm en
français` 390, `download` 110 (+750%), `alternative` 90. `IA privée` 50, `IA
auto-hébergée` below threshold. Canada's French demand for our category is
nil: every French term except `notebooklm en français` (110) came back below
threshold in the Canada pull. `fr-CA` hreflang on the French pages is enough.

**Spain, Mexico.** The demand is brand: `notebooklm gratis` 2,900 in Mexico
(+5,043%, 4,400 → 3,600 → 3,600) and 880 in Spain, `en español` 1,000 + 590
(Spain) + 320 (Mexico), `app` 880 + 320, `descargar` 210 + 140 + 170 + 110,
`precio` 140 + 140. Category terms are thin and Spain-only: `IA local` 320
(KD 0, +243%), `IA en local` 170, `IA privada` 170 (KD 0), `IA open source`
140, `LLM local` 110; in Mexico `IA local` is below threshold. `IA para
abogados` 390 + 390 is the legal vertical's best non-English showing.
`notebooklm alternatives` is 50 in Spain, at a $35.59 CPC. Brand heads are
823K and 368K at $0.74-1.22. One `/es/` set, `es` and `es-MX` hreflang,
three pages.

**Brazil.** The second largest NotebookLM audience (1.22M, +308%). Brand:
`em português` 1,300, `download` 1,000 (+519%), `app` 720, `gratuito` 480
(+2,100%), `preço` 320, `baixar notebooklm` 320 (+191%). Category in
Portuguese: `IA open source` 590, `IA local` 390 (KD 0, +414%, steady at
720), `IA offline` 320 (KD 0, +129%), `LLM local` 320 (+182%), `IA para
documentos` 210 (+191%), `LGPD IA` 90, `IA de código aberto` 90 (+325%),
`rodar IA localmente` 90, `IA privada` 70 (+750%); `Obsidian AI` 720 and
`Obsidian IA` 590 (+529%). Median CPC $1.29. Same three pages as Spanish;
`pt-BR` hreflang, no `pt-PT` variant (Portugal was not pulled and Brazil is
20x its size).

**Canada, Australia, Singapore, UAE, New Zealand, South Africa, Philippines,
Indonesia.** English, the UK's shape at smaller scale: `local llm` (880
Canada, 590 Australia), `open source ai` (720, 590, 720 Indonesia), `obsidian
ai` (590 Canada +376%, 480 Australia +488%, 720 Indonesia +1,018%, 320
Singapore +556%), then the brand download/free pair. Canada has the highest
CPCs outside the US (`ai for lawyers` $39.71, `is notebooklm free` $11.19,
median $4.54) and `sovereign ai` 480 at $13.36; Australia `sovereign ai` 480
at $11.63. Indonesia and the Philippines have big brand audiences (550K,
165K), `ai research assistant` 590 each (+809%, +243%) and `notebooklm
download` climbing fast (Indonesia 210 running 390 → 590 → 720; Philippines
170, +1,100%). Hreflang only.

**Taiwan, Italy, Netherlands, Poland, Sweden.** Taiwan is brand-only:
`NotebookLM 下載` 1,900 (KD 11), `中文` 880, `app` 480, `教學` (tutorial)
6,600, `AI 資安` 260; every Chinese category term tried is below threshold
while `ollama` is 33,100, so the technical audience searches in English.
Italy: `in italiano` 880 + 170, `AI open source` 720, `app` 590, `download`
390, `gratis` 260 (+250%), `IA per avvocati` 210 at $7.66, `AI offline` 170,
`Obsidian AI` 320 (+457%); `IA locale` 50 and `IA privata` below threshold.
Netherlands: 92% English, `lokale AI` 40, `AVG AI` 20 at $14.56, `AI voor
advocaten` 50 at $15.25. Poland: `AI dla prawników` 590 (KD 3) is the only
Polish term with volume beyond `notebooklm po polsku` 170. Sweden: 90%
English, `lokal AI` 40, `AI för jurister` 50. English pages with hreflang;
Taiwan's download string is the one to localise if `/downloads` gets a
string-localised variant, and Italy is the next Tier 3 candidate.

## Studio outputs abroad

`01`, section 3, sizes the eleven Studio formats in the US. The same list
(translated for Japan and Germany, with the local study vocabulary added for
the UK and India) went through Keyword Overview in the four markets that
matter for it: `data/artifacts-intl-{gb-en,in-en,de-de,jp-ja}.json`. Japan's
KD column is mostly the `~` proxy or blank; Google has no difficulty score for
most Japanese terms.

| market | biggest artifact pool | study vocabulary | flashcards / quiz | NotebookLM-branded artifact terms |
|---|---|---|---|---|
| **Japan** | slides 18,600 (`スライド 作成 ai` 14,800 at **KD 15**, `パワポ 作成 ai` 3,600, `ai プレゼン 作成` 210); summary 10,800 at KD 1-11 (`要約 ai` 5,400 at **KD 1**, `youtube 要約 ai` 2,900, `論文 要約 ai` 1,000, `pdf 要約 ai` 590, `文章 要約 ai` 590) | `勉強 ai` 4,400 (KD 3~), `notebooklm 使い方 勉強` 390, `notebooklm 勉強` 320, `勉強 ai アプリ` 110 (+175%) | none; `ai 問題作成` 260 is the only quiz form and no flashcard phrasing returned | larger than the US: `notebooklm スライド` 1,000 (US 170), `インフォグラフィック` 880 (US 210, +425%), `マインドマップ` 480 (US 320), `動画解説` 480 |
| **Germany** | slides 9,400 (`präsentation erstellen ki` 5,400 at **KD 11**, `powerpoint ki` 2,400, `ki powerpoint erstellen` 1,600 at KD 5) | **Lernzettel** = study guide (`lernzettel erstellen ki` 1,000, `lernzettel ki` 140); `ki zum lernen` 880 (+86%), `lernen mit ki` 480, `ki für studenten` 260 (KD 7, +91%), `ki für schüler` 140 | **Karteikarten** 1,190 across three forms (`ki karteikarten erstellen` 480, `karteikarten erstellen ki` 390, `karteikarten ki` 320); quiz ~240 across five forms | `notebooklm video` 110, `mindmap` 70, `infografik` 30 |
| **India** | slides 97,000 but generic and KD 58-73 (`ai ppt maker` 60,500, `ai presentation maker` 22,200, `ai ppt generator` 12,100), plus `pdf to ppt` at 201,000, a converter; summary (`youtube video summarizer` 9,900 at KD 20, `pdf summarizer` 2,400 at KD 14) | `best ai for studying` 4,400 (**+184%**), `ai for studying` 2,400, `ai tools for students` 1,600, `ai study tools` 1,300 (+81%), `ai for exam preparation` 260; `notebooklm for studying` 720 (**+3233%**), `notebooklm for students` 590 (+700%) | `flashcard generator` 2,400, `ai quiz generator` 1,300, `pdf to quiz` 390 at **KD 10**, `ai mcq generator` 140 | `notebooklm slides` 90 (+800%), `flashcards` 90 (+350%), `quiz` 50 (+200%) |
| **UK** | `flashcard generator` 5,400 (8,100 in term), `pdf to ppt` 8,100, `ai presentation maker` 2,400 | **revision**: `flashcards for revision` 1,900 at **KD 1**, `revision ai` 320 (KD 11), `ai revision tool` 210, `best ai for revision` 90, `ai for revision` 50; `best ai for studying` 320 (+55%) | `ai quiz generator` 480 (KD 24), `ai flashcard generator` 590, `ai flashcard maker` 480 | `notebooklm video overview` 90, `infographic` 70 |

Five things follow.

1. **Japan strengthens its own case.** Slides and summary add 29,000 a month
   of near-zero-KD Japanese demand to a market that was already the largest
   gap between demand and competition in the research, and the Japanese
   NotebookLM audience searches for the artifacts by name more than the US
   one does. The `/ja/` set gains a slides page and a summary page; the
   English feature pages for flashcards and quiz are *not* translated,
   because no Japanese phrasing for either returned volume.
2. **Germany has a study market in its own words.** *Lernzettel*,
   *Karteikarten*, *Zusammenfassung*, *Präsentation erstellen*: none of
   these is a translation of the US term, and the English forms are tiny
   (`flashcard generator` 320 at KD 71, `ai summarizer` 320 at KD 64,
   `study guide maker` 10). The `/de/` set gains a slides page and a
   *Lernzettel* page that bundles Karteikarten and Zusammenfassung.
3. **India is the growth market for the study hub and needs nothing new.**
   Every NotebookLM-study term is growing three to thirty-fold, `best ai
   for studying` is 3.4x the US figure, and it is all in English at US-like
   KD. The English hub serves it through hreflang; India's converter demand
   (`pdf to ppt`, 201,000) is not ours anywhere.
4. **The UK needs one word, not a page.** *Revision* carries the UK study
   intent and appears in no US pull; `flashcards for revision` alone is
   1,900 at KD 1. One H2 on the English flashcards page (`02`). The
   exam-brand phrasings we tried (GCSE, A-level, past papers) returned no
   volume.
5. **Slides is an international product, summary is a Japanese one.** In the
   US both heads are owned by Canva, Adobe and QuillBot at KD 33-84 and
   falling; in Japan and Germany the same jobs are KD 1-15 in the local
   language. Build the English slides page as the parent of `/ja/` and
   `/de/` pages, and write the summary page only in Japanese.

## Glossaries

Per language, the term with volume for each concept we write about. Use these
words in titles, H1s and meta descriptions; the English term is the fallback
where the row says so.

**Japanese (JP 57,800)**

| concept | term | recent | KD | CPC $ | yoy |
|---|---|---|---|---|---|
| local LLM | ローカルLLM | 22,200 (33-40K/mo) | 0 | 1.98 | +174% |
| local AI | ローカルAI | 5,400 | 0 | 1.89 | +326% |
| pricing | NotebookLM 料金 | 8,100 | 3 | 3.55 | +50% |
| free | NotebookLM 無料 | 1,900 | 22 | 1.80 | +48% |
| app | NotebookLM アプリ | 2,900 | 13 | 2.32 | |
| download | NotebookLM ダウンロード | 1,000 | 22 | 2.46 | +319% |
| how to | NotebookLM 使い方 | 27,100 | 6 | 1.17 | +50% |
| offline | オフラインAI | 590 | 0 | 2.42 | +85% |
| open source | オープンソースAI | 590 | 2 | 3.21 | +126% |
| data leakage | 生成AI 情報漏洩 | 480 | 0 | 2.38 | |
| security | 生成AI セキュリティ | 320 | 0 | 7.12 | |
| on-prem | オンプレミスAI / オンプレAI | 210 / 210 | — | 4.91 / 3.99 | +86% / +53% |
| PDF summary | PDF 要約 AI | 590 | 0 | 2.10 | |
| summary | 要約 AI | 4,400 (5,400) | 1 | 2.11 | −45% |
| YouTube summary | YouTube 要約 AI | 2,900 | 10~ | 1.16 | −19% |
| paper summary | 論文 要約 AI | 1,000 | 11~ | 2.70 | −45% |
| slides | スライド作成 AI | 14,800 | 15 | 2.47 | |
| PowerPoint | パワポ作成 AI | 3,600 | — | 2.99 | −21% |
| studying | 勉強 AI | 4,400 | 3~ | 2.33 | |
| NotebookLM slides / infographic / mind map | NotebookLM スライド / インフォグラフィック / マインドマップ | 480 / 480 / 320 | 14~ / 9~ / 5~ | 2.33 / — / — | +50% / +425% / −65% |
| local RAG | ローカルRAG | 170 | — | 5.83 | |
| PKM | Obsidian AI | 1,600 | 0 | 2.42 | |
| flashcards, quiz | no Japanese phrasing returned; `AI 問題作成` 260 is the nearest | | | | |
| alternative, private, self-hosted, air-gapped | below threshold; use ローカルLLM | | | | |

**German (DE 16,800 · AT 760 · CH 1,170)**

| concept | term | recent | KD | CPC $ | yoy |
|---|---|---|---|---|---|
| open source | open source KI | 1,300 | 5 | 3.83 | +116% |
| local AI | lokale KI | 720 (880 → 1,300) | 0 | 4.60 | +400% |
| privacy | KI Datenschutz | 480 | 19 | 7.01 | |
| local LLM | lokale LLM / lokales LLM | 320 / 210 | 0 | 3.50 / 3.20 | +179% / +136% |
| run locally | KI lokal betreiben | 260 | 0 | 1.84 | +52% |
| offline | offline KI | 260 | 0 | 2.09 | +53% |
| GDPR | DSGVO konforme KI | 260 | 0 | 11.79 | +255% |
| legal | KI für Anwälte | 320 | 0 | 12.25 | +88% |
| self-host | KI selbst hosten | 140 | — | 3.01 | |
| free | notebooklm kostenlos | 320 | 8 | 1.04 | +143% |
| price | notebooklm Preis | 210 | 5 | 1.12 | +100% |
| alternative | notebooklm alternative (English) | 320 | 0 | 3.82 | |
| in German | notebooklm deutsch | 320 | 13 | 0.87 | −80% |
| PKM | Obsidian KI | 320 | 5 | 4.81 | +929% |
| slides | Präsentation erstellen KI | 2,900 (5,400) | 11 | 1.64 | |
| PowerPoint | KI PowerPoint erstellen / PowerPoint KI | 880 / 1,000 | 5 / 39~ | 1.88 / 2.17 | −18% / −28% |
| study guide | Lernzettel erstellen KI | 880 | 18~ | 2.32 | −33% |
| studying | KI zum Lernen / lernen mit KI | 720 / 390 | 14 / 13 | 3.36 / 2.80 | +86% / −18% |
| students | KI für Studenten | 260 | 7 | 2.97 | +91% |
| flashcards | Karteikarten erstellen KI (3 forms) | 970 | 33~ | 2.70-3.18 | −34% to −65% |
| summary | KI Zusammenfassung / PDF zusammenfassen KI | 590 / 320 | 11 / 14~ | 1.94 / 1.55 | −33% / −84% |
| mind map | Mindmap erstellen KI | 170 | 2 | 2.39 | −57% |
| quiz | Quiz erstellen KI | 70 | — | 3.68 | −33% |
| sovereign, on-prem, air-gapped, "ohne Internet" | below threshold; use lokale KI and DSGVO | | | | |

**French (FR 9,900)**

| concept | term | recent | KD | CPC $ | yoy |
|---|---|---|---|---|---|
| free | notebooklm gratuit | 1,900 | 7 | 1.63 | +122% |
| open source | IA open source | 880 | 0 | 2.92 | +49% |
| local AI | IA locale / IA en local | 590 / 260 | 0 | 6.32 / 2.29 | +243% / +86% |
| local LLM | LLM local | 390 | 0 | 4.17 | +88% |
| sovereign | IA souveraine | 480 | 0 | 3.28 | |
| podcast | podcast IA | 390 | 0 | 1.37 | |
| GDPR | IA RGPD / RGPD IA | 140 / 110 | 6 / 3 | 7.23 / 10.30 | +57% |
| legal | IA pour avocats | 90 | 8 | 8.84 | +125% |
| in French | notebooklm en français | 390 | 12 | 2.46 | |
| private, self-hosted, offline, on-prem | below threshold (`IA privée` 50); use IA locale | | | | |

**Spanish (ES 6,180 · MX 5,690)**

| concept | term | recent | KD | CPC $ | market |
|---|---|---|---|---|---|
| free | notebooklm gratis | 2,900 / 880 | 18 / 66 | 0.74 / 1.22 | MX / ES |
| in Spanish | notebooklm en español | 1,000 / 320 | 25 / 16 | 1.94 / 0.90 | ES / MX |
| download | notebooklm descargar / descargar notebooklm | 210 + 140 / 170 + 110 | 18 / 7 | 0.90 / 1.04 | ES / MX |
| price | notebooklm precio | 140 / 140 | 0 / — | 0.62 / 1.64 | ES / MX |
| legal | IA para abogados | 390 / 390 | 15 / 1 | 5.29 / 1.47 | ES / MX |
| local AI | IA local / IA en local | 320 / 170 | 0 / 0 | 2.56 / 4.46 | ES only |
| private | IA privada | 170 | 0 | 1.88 | ES |
| documents | IA para documentos | 70 / 170 | 4 / 8 | 1.38 / 1.32 | ES / MX |
| open source, offline, self-hosted, alternative | below threshold; use English `local llm` (170 ES) | | | | |

**Portuguese (BR 9,540)**

| concept | term | recent | KD | CPC $ | yoy |
|---|---|---|---|---|---|
| in Portuguese | notebooklm em português | 1,300 | 13 | 1.08 | +23% |
| download | notebooklm download / baixar notebooklm | 1,000 / 320 | 17 / 14 | 0.88 / 0.97 | +519% / +191% |
| free | notebooklm gratuito | 480 | 13 | 0.63 | +2,100% |
| price | notebooklm preço | 320 | 0 | 1.34 | |
| open source | IA open source | 590 | 20 | 1.90 | +85% |
| local AI | IA local | 390 (steady 720) | 0 | 0.73 | +414% |
| local LLM | LLM local | 320 | 9 | 3.23 | +182% |
| offline | IA offline | 320 | 0 | 0.24 | +129% |
| documents | IA para documentos | 210 | 0 | 1.38 | +191% |
| LGPD | LGPD IA | 90 | — | 3.34 | |
| PKM | Obsidian IA | 590 | 21 | 5.73 | +529% |
| private, self-hosted, sovereign, alternative | below threshold (`IA privada` 70) | | | | |

**Shorter lists.** Korean: `오픈소스 AI` 480, `오픈소스 LLM` 390, `온프레미스
AI` 140, `오프라인 AI` 170, `NotebookLM 가격` 210, `무료` 140, `다운로드` 170,
`사용법` 1,600; the local-LLM concept in English. Traditional Chinese:
`NotebookLM 下載` 1,900, `中文` 880, `免費` 170, `教學` 6,600, `AI 資安` 260;
nothing else. Italian: `AI open source` 720, `in italiano` 880, `gratis` 260,
`IA per avvocati` 210, `AI offline` 170, `LLM locale` 90. Dutch: `AI voor
advocaten` 50, `lokale AI` 40, `AVG AI` 20. Polish: `AI dla prawników` 590,
`po polsku` 170, `AI offline` 170. Swedish: `AI för jurister` 50, `lokal AI`
40.

## URL, hreflang and engine plan

**Structure.** Language subdirectories on the one domain: `/ja/`, `/de/`,
`/fr/`, `/es/`, `/pt-br/`. Subdirectories inherit surfsense.com's authority
(too little to split across ccTLDs or subdomains; see `04`), and the Next.js
`app/[locale]/` convention fits `portal/02-pages.md`. English is the root,
with `x-default` pointing at it.

**hreflang.** One English page serves every English market; do not create
`en-GB` or `en-IN` copies, they would be duplicates. Each localised page
declares its language plus the regional variants it serves:

| page language | hreflang values | served markets |
|---|---|---|
| English | `en`, `x-default` | US, UK, CA, AU, IN, IE, SG, NZ, ZA, AE, PH, ID, and every market without a localised page |
| Japanese | `ja` | Japan |
| German | `de`, `de-AT`, `de-CH` | Germany, Austria, Switzerland |
| French | `fr`, `fr-CA` | France, Canada |
| Spanish | `es`, `es-MX`, `es-419` | Spain, Mexico, Latin America |
| Portuguese | `pt-BR`, `pt` | Brazil, Portugal |

Every page in a language set links to every other version and to itself, and
`sitemap.xml` carries the same alternates. Translated pages get their own
`<title>`, meta description, H1 and Open Graph text from the glossaries above,
not a machine translation of the English metadata.

**What gets translated per tier.** Tier 2: home, downloads, pricing, one
quickstart, the compliance section (JP: 情報漏洩 and セキュリティ; DE: DSGVO),
the legal page (DE). Tier 3: home, downloads, free/pricing FAQ. Never: the
blog, API and plugin docs, the changelog. The downloads page renders from the
release manifest, so localising it is a string file, and the same file gives
Taiwan its `下載` string later.

**Engines.** Google is 90%+ of search in every market pulled except Korea
(Naver ~50%) and, marginally, Japan (Yahoo Japan ~15%, powered by Google's
index, so Google rankings carry over). Bing serves DuckDuckGo, Ecosia and
Yahoo outside Japan, and the privacy-search audience overlaps ours more than
average: submit the sitemap to Bing Webmaster Tools and use IndexNow on
release. Brave Search runs its own index; nothing to submit, but the site
must render without JavaScript for it to crawl the content, which static
portal pages do. Naver and Baidu are out of scope: Korea is Tier 4, China was
not pulled and is not a market for a product sold in dollars anyway.

**Measurement.** Google Search Console, one property, filtered by country;
Bing Webmaster Tools. Re-pull the grid quarterly with the two commands in
`data/README.md` (27 API calls) and diff `intl/markets.csv`. Watch:
`ローカルLLM` (whether 33-40K holds), `lokale KI`, `IA local` in Brazil,
`notebooklm download` in India and Indonesia, the US spike decay on `private
ai` and `local llm`, and whether `notebooklm alternative` appears in any
Asian market, where it is still below threshold everywhere.

## What this changes in the other documents

- `02-page-briefs.md`: one hreflang section up front, the first-screen
  vocabulary rule, an international note on the downloads and pricing briefs,
  and the German-page section becomes the localisation order (Japan, Germany,
  then the three-page tier). No US brief changes.
- `00d-pivot-plan.md`: B6 points here for the launch items (hreflang block,
  first-screen words); localisation is logged under After the MVP in tiers,
  not as an open decision; Japan first, Germany second.
- `01-keyword-research.md`: the US-only caveat is resolved by this file.
- `data/README.md`: the 27 pulls are archived under `data/intl/` with the two
  commands that regenerate them, replacing the earlier "responses read
  inline, not archived" note.
- Studio pass ("Studio outputs abroad"): `02`'s Japan and Germany entries
  gain the slides, summary and Lernzettel pages; the English flashcards page
  gets a *revision* H2 for the UK; nothing is added for India.

## Method

`data/intl/lists.json` holds the English core and extended lists (shared by
all 27 pulls) and one translated list per language, with a `markets` map of
`location_code`, `language_code` and which lists each market gets. Each pull
is a single `keyword_overview/live` task; the response is compacted with
`parse.py --compact-from <raw.json> --market <id>` into
`data/intl/<market>.json`, keeping volume, CPC, KD, yoy, intent, the top-10
backlink profile and the last 12 months, and recording which requested
keywords came back empty under `missing`. The compactor refuses a response
whose echoed `location_code` or `language_code` does not match the market.
`parse.py --mode markets --csv intl/markets.csv` writes the per-market
summary, the concept-by-market pivot and the long table, with `variant_of`
marking the spellings Google Ads merged. `parse.py --self-check` covers the
trimming, variant folding and totals.

Translations were written as the phrases a native speaker would type, not as
translations of the English list, and the below-threshold results in finding
9 are the check on that: where a phrase came back empty, the concept is not
searched in that language, and the glossary says what is.

The Studio pass used the same endpoint for four markets with an artifact list
(`data/artifacts-intl-<market>.json`, 28-48 rows each). These four were
archived by hand in the same compact shape, minus the `missing` field, so
the requested-but-empty phrasings for them (Japanese flashcard and quiz
forms, UK exam brands) are recorded in this document rather than in the
file. Re-pulling them through `--compact-from` will add the field.
