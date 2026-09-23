<!--
  सनसेट कॉलआउट समय-सीमित है। 18 अक्टूबर 2026 को, जब एक्सपोर्ट विंडो बंद हो जाएगी,
  इसे और नीचे दिए गए "होस्टेड ऐप से इम्पोर्ट करना" लिंक को हटा दें।
  यह फ़ाइल README.md को सेक्शन-दर-सेक्शन फ़ॉलो करती है।
  इस पेज का तर्क: plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Forks](https://img.shields.io/github/forks/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/network/members)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img width="128" height="128" alt="SurfSense, एयर-गैप्ड, ओपन-सोर्स NotebookLM विकल्प" src="surfsense_web/public/homepage/icon.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>एयर-गैप्ड, ओपन-सोर्स NotebookLM विकल्प।</b>
    <br />
    जो दस्तावेज़ आप अपलोड नहीं कर सकते, उन्हें ब्रीफ़िंग, स्लाइड डेक, रिपोर्ट, स्टडी गाइड और पॉडकास्ट में बदलें — पूरी तरह अपनी ही मशीन पर।
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>डाउनलोड</b></a> ·
    <a href="https://www.surfsense.com/docs">डॉक्स</a> ·
    <a href="#surfsense-क्या-बनाता-है">यह क्या बनाता है</a> ·
    <a href="#surfsense-की-तुलना-दूसरों-से">तुलना</a> ·
    <a href="https://www.surfsense.com/pricing">प्राइसिंग</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | हिन्दी | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

<p align="center">
  <img src="surfsense_web/public/homepage/offline-studio.png" alt="SurfSense डेस्कटॉप ऐप, जिसमें Studio खुला है और Qwen चुना गया है, लोकल स्रोतों को आर्टिफैक्ट में बदलते हुए" />
</p>

SurfSense एक मुफ़्त, ओपन-सोर्स डेस्कटॉप ऐप है, उन दस्तावेज़ों के लिए जो पहले से आपके पास हैं। उन्हें ऐप में डालें, सवाल पूछें और ऐसे जवाब पाएँ जो अपने स्रोत का हवाला देते हैं; फिर उन्हीं दस्तावेज़ों को ब्रीफ़िंग, स्लाइड डेक, रिपोर्ट, स्टडी गाइड या पॉडकास्ट में बदल दें। यह सब आपकी अपनी मशीन पर चलता है: इंडेक्स आपकी डिस्क पर रहता है, मॉडल आप चुनते हैं, और ऐप कुछ भी अपलोड नहीं करता। कोई अकाउंट बनाने की ज़रूरत नहीं।

**शुरुआत करें।** अपनी मशीन के लिए इंस्टॉलर डाउनलोड करें, फिर अपनी खुद की मॉडल API key लगाएँ या ऐप को अपने लिए एक लोकल मॉडल डाउनलोड करने दें।

| प्लैटफ़ॉर्म | डाउनलोड |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-Setup.exe) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-arm64.dmg) |
| **Linux** x64 (AppImage) | [SurfSense.AppImage](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.AppImage) |
| **Linux** x64 (deb) | [SurfSense.deb](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.deb) |

हर लिंक सबसे नए रिलीज़ का परमालिंक है। आप [surfsense.com/downloads](https://www.surfsense.com/downloads) से भी चुन सकते हैं या [सभी रिलीज़](https://github.com/MODSetter/SurfSense/releases) देख सकते हैं। AppImage अपने आप अपडेट हो जाता है; deb नहीं होता।

> [!NOTE]
> **होस्टेड वेब ऐप इस्तेमाल करते थे?** उसे बंद किया जा रहा है। एक बार उसे खोलकर अपने वर्कस्पेस एक्सपोर्ट करें, फिर वह बंडल डेस्कटॉप ऐप में इम्पोर्ट कर लें; दस्तावेज़, फ़ोल्डर, टाइटल और चैट थ्रेड — सब साथ आ जाते हैं। एक्सपोर्ट विंडो 18 अक्टूबर 2026 को बंद हो जाएगी। पूरी जानकारी [सनसेट पेज](https://www.surfsense.com/sunset) पर है।

## SurfSense क्या बनाता है

कुछ दस्तावेज़ चुनें और एक फ़ॉर्मैट चुनें। ऐप उसे आपके चुने हुए स्रोतों से, आपकी ही मशीन पर तैयार करता है।

| फ़ॉर्मैट | क्या मिलता है | क्या चाहिए |
|---|---|---|
| **सारांश** | चुने हुए स्रोतों का एक व्यवस्थित ब्रीफ़ | जनरेशन मॉडल |
| **फ़्लैशकार्ड** | एक इंटरैक्टिव डेक, एक बार में एक कार्ड | जनरेशन मॉडल |
| **क्विज़** | जवाबों के साथ बहुविकल्पीय सवाल | जनरेशन मॉडल |
| **माइंड मैप** | ज़ूम और कोलैप्स होने वाला Markmap | जनरेशन मॉडल |
| **स्लाइड्स** | एडिट होने लायक `.pptx`, डेक की तस्वीर भर नहीं | जनरेशन मॉडल |
| **दस्तावेज़** | एडिट होने लायक `.docx` रिपोर्ट | जनरेशन मॉडल |
| **स्प्रेडशीट** | स्रोतों से निकाली गई टेबल्स का `.xlsx` | जनरेशन मॉडल |
| **वेब पेज** | अपने आप में पूरा एक HTML पेज | जनरेशन मॉडल |
| **PDF** | टाइपसेट किया हुआ PDF | जनरेशन मॉडल |
| **पॉडकास्ट** | दो होस्ट की ऑडियो बातचीत, जिसे Kokoro-82M ऑफ़लाइन आवाज़ देता है | जनरेशन मॉडल + साथ आने वाली आवाज़ |
| **इमेज** | सामग्री के लिए एक इलस्ट्रेशन | इमेज मॉडल + जनरेशन मॉडल |
| **इन्फ़ोग्राफ़िक** | एक ही पैनल में विज़ुअल सारांश | इमेज मॉडल + जनरेशन मॉडल |

कुछ काम एक से ज़्यादा फ़ॉर्मैट माँगते हैं। स्टडी गाइड यानी एक ही स्रोत-सेट पर सारांश, फ़्लैशकार्ड डेक और क्विज़; और क्लाइंट ब्रीफ़िंग आम तौर पर वह डेक होती है जिससे आप प्रेज़ेंट करते हैं, साथ में वह सारांश जो आप बाद में भेजते हैं। वीडियो ओवरव्यू अभी नहीं बने हैं।

## सब कुछ आपकी मशीन पर ही रहता है

लोग इसे केस पेपर, क्लाइंट वर्किंग पेपर, इंटरव्यू ट्रांसक्रिप्ट, अंदरूनी स्पेसिफ़िकेशन, अप्रकाशित रिसर्च और एक पूरे सेमेस्टर के लेक्चर नोट्स पर लगाते हैं। आप इन सब पर एक साथ सवाल पूछ सकते हैं, और हर जवाब उस स्रोत का हवाला देता है जहाँ से वह आया है। ऐप इनमें से कुछ भी अपलोड नहीं करता।

- **इंडेक्स लोकल है।** पार्सिंग, चंकिंग और एम्बेडिंग आपके कंप्यूटर पर ही होती है, और `~/.surfsense` के अंदर SQLite में जाती है। SurfSense न उसकी कोई कॉपी रखता है, न इसका कोई लॉग कि आपने क्या पूछा।
- **हर हिस्सा लोकल चल सकता है।** डॉक्यूमेंट पार्सर, रिट्रीवल मॉडल और पॉडकास्ट की आवाज़ इंस्टॉलर के अंदर ही आते हैं। चैट और इमेज जनरेशन लोकल सर्वर के रूप में आते हैं, जिनके वेट आप एक बार डाउनलोड करते हैं — यानी बिना किसी अकाउंट या API key के आप टेक्स्ट, ऑडियो और तस्वीरें बना सकते हैं। हम इसकी जाँच नेटवर्क बंद करके एक PDF इनजेस्ट करके करते हैं।
- **बाहर जाने वाले कनेक्शन डिफ़ॉल्ट रूप से बंद हैं।** एक एग्रेस पैनल उन सभी जगहों की सूची देता है जहाँ तक ऐप पहुँच सकता है, और जिन्हें आप चाहें सिर्फ़ उन्हें चालू करते हैं।
- **न टेलीमेट्री, न क्रैश रिपोर्टिंग।** कुछ भी पीछे से हमें रिपोर्ट नहीं भेजता, इसलिए ऑप्ट-आउट ढूँढने की नौबत ही नहीं आती।

SurfSense यह नहीं बता सकता कि इससे कोई खास नियम-कायदा पूरा होता है या नहीं। वह आपके अपने कंट्रोल्स और आपके रेगुलेटर पर निर्भर करता है। ऐप बस इतना बता सकता है कि आपके दस्तावेज़ किस मशीन पर हैं।

## SurfSense की तुलना दूसरों से

तीन तरह के प्रोडक्ट को “लोकल NotebookLM” कहा जाता है, और तीनों अलग-अलग सवालों के जवाब देते हैं। इनमें कोई भी खराब टूल नहीं है; बस आखिर में आपके हाथ अलग-अलग चीज़ें लगती हैं।

**बनाम Jan, AnythingLLM, Open WebUI, LM Studio।** ये मॉडल को लोकल चलाते हैं और उससे चैट करने की जगह देते हैं। SurfSense अगला सवाल हल करता है: उससे एक तैयार दस्तावेज़ कैसे निकालें? चाहें तो दोनों साथ इस्तेमाल करें — SurfSense को किसी भी OpenAI-कम्पैटिबल एंडपॉइंट पर लगा दें, इनमें से किसी एक पर भी।

**बनाम RemNote, Quizlet, NoteGPT, StudyFetch, Gamma।** ये आर्टिफ़ैक्ट बनाते ज़रूर हैं, और कुछ तो हमारे से बेहतर दिखते भी हैं। सौदा यह है कि आपकी सामग्री कहाँ जाती है: आप उसे अपलोड करते हैं, हर महीने पैसे देते हैं, और आपकी फ़ाइलें किसी और के अकाउंट में रहती हैं।

**बनाम Google NotebookLM।** उसमें फ़्लैशकार्ड, क्विज़, माइंड मैप और ऑडियो ओवरव्यू पहले से हैं, तो दोनों लगभग एक जैसी चीज़ें बनाते हैं। फ़र्क़ इतना है कि काम किसकी मशीन पर होता है और आप उस पर कौन-सा मॉडल लगा सकते हैं।

| | Google NotebookLM | SurfSense |
|---|---|---|
| ऑफ़लाइन / एयर-गैप्ड चलता है | नहीं | **हाँ** |
| आपके दस्तावेज़ आपकी मशीन से बाहर जाते हैं | हाँ | **नहीं** |
| अकाउंट ज़रूरी है | Google अकाउंट | **कोई नहीं** |
| ओपन सोर्स | नहीं | **Apache-2.0** |
| कीमत | फ़्री टियर; Pro $19.99 प्रति माह; Ultra $249.99 प्रति माह | **ऐप मुफ़्त है** |
| मॉडल | सिर्फ़ Gemini | कोई भी OpenAI-कम्पैटिबल API, या कोई लोकल मॉडल |
| स्रोतों की सीमा | 50 से 600 स्रोत, हर एक में 500,000 शब्द | जितना आपकी डिस्क में समाए |
| ऑडियो और वीडियो ओवरव्यू | हाँ, और बेहतर | ऑडियो हाँ, वह भी ऑफ़लाइन; वीडियो अभी नहीं |

ऑडियो क्वालिटी में NotebookLM आगे है, और उसके पास वीडियो भी है। अगर आपको अपने स्रोतों का Google के सर्वर पर पड़े रहना ठीक लगता है, तो उसे इस्तेमाल करें। अगर नहीं, तो यह उसी तरह का टूल है, बस अपलोड किए बिना।

## झटपट शुरुआत

आपको न Docker चाहिए, न टर्मिनल, न GPU और न कोई compose फ़ाइल।

1. **इंस्टॉलर डाउनलोड करें** ऊपर दी गई टेबल से। वह साइन किया हुआ है, इसलिए आपका OS अड़ंगा नहीं लगाएगा।
2. **मॉडल चुनें।** ऐप से कोई लोकल मॉडल डाउनलोड करवा लें (Qwen3, छह साइज़ में, 0.5 GB से शुरू) या किसी भी OpenAI-कम्पैटिबल API का बेस URL और key पेस्ट कर दें। पिकर कोई मॉडल सुझाने से पहले जाँच लेता है कि आपकी मशीन उसे चला पाएगी या नहीं, और आप जो भी key देते हैं वह एन्क्रिप्टेड रूप में सेव होती है, जिसका सीक्रेट आपके OS कीचेन में रहता है।
3. **दस्तावेज़ डालें।** ऐप PDF, Office फ़ाइलें और इमेज आपकी ही मशीन पर पार्स करता है।
4. **सवाल पूछें।** हर जवाब उस स्रोत का हवाला देता है जहाँ से वह आया है।
5. **Studio खोलें,** फ़ॉर्मैट चुनें, फ़ाइल ले लें।

धीमा हिस्सा सिर्फ़ डाउनलोड है, क्योंकि इंस्टॉलर के साथ पार्सर, रिट्रीवल मॉडल, पॉडकास्ट की आवाज़ और लोकल मॉडल सर्वर भी आते हैं, ताकि नेटवर्क बंद होने पर भी ऐप काम करे।

## डॉक्स और कम्युनिटी

ऐप और उसके अपडेट मुफ़्त हैं। लाइसेंस से प्लगइन और प्रायॉरिटी सपोर्ट मिलते हैं, इसके अलावा वह कुछ नहीं रोकता — यानी लाइसेंस खत्म हो जाने पर भी ऐप और आने वाला हर अपडेट आपके पास बना रहता है। देखें [प्राइसिंग](https://www.surfsense.com/pricing)।

इस रिपो का Docker स्टैक (`surfsense_backend`, `surfsense_web`, compose फ़ाइलें) ओपन सोर्स और इंस्टॉल करने लायक बना रहेगा, और वह **कम्युनिटी-सपोर्टेड है: न कोई SLA, न पीछे कोई होस्टेड सर्विस।** नए यूज़र्स के लिए सपोर्टेड रास्ता डेस्कटॉप ऐप है।

- इंस्टॉल, मॉडल, Studio फ़ॉर्मैट और सेल्फ़-होस्टिंग के लिए [डॉक्युमेंटेशन](https://www.surfsense.com/docs)
- [होस्टेड ऐप से इम्पोर्ट करना](https://www.surfsense.com/sunset)
- होस्टेड स्क्रेपर API के लिए [MCP सर्वर](./surfsense_mcp)
- मदद और आइडिया के लिए [Discord](https://discord.gg/ejRNvftDp9), दिशा तय करने के लिए [Discussions](https://github.com/MODSetter/SurfSense/discussions), और दोबारा दोहराए जा सकने वाले बग के लिए [Issues](https://github.com/MODSetter/SurfSense/issues)
- आगे यह कहाँ जाता है, इस पर नज़र रखनी हो तो **रिपो को स्टार करें**

## योगदान कैसे करें

पुल रिक्वेस्ट का स्वागत है, और [CONTRIBUTING.md](CONTRIBUTING.md) पूरी प्रक्रिया समझाता है। संक्षेप में:

- **काम चुनें:** [`good first issue`](https://github.com/MODSetter/SurfSense/labels/good%20first%20issue) या [`help wanted`](https://github.com/MODSetter/SurfSense/labels/help%20wanted) लेबल वाला कोई issue, या [`docs/architecture/`](docs/architecture/overview.md) के हर डॉक के आख़िर में दी गई Known gaps (ज्ञात कमियाँ) सूची की कोई पंक्ति।
- **पहले समझें कि यह कैसे काम करता है:** [`docs/`](docs/README.md) हर फ़ीचर को और उसे इस तरह बनाने की वजह समझाता है, और [`docs/ROADMAP.md`](docs/ROADMAP.md) बताता है कि मेंटेनर किस पर काम कर रहे हैं।
- **`dev` ब्रांच पर PR खोलें।** बग फ़िक्स और डॉक्स के लिए पहले चर्चा ज़रूरी नहीं है; नया फ़ीचर एक छोटे डिज़ाइन प्रस्ताव से शुरू होता है। डेस्कटॉप ऐप [`surfsense_local/`](./surfsense_local) में है और उसका README डेवलपमेंट लूप समझाता है।

हमारे सभी Surfers का शुक्रिया:

<p align="center">
  <a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="SurfSense में योगदान देने वाले लोग" />
  </a>
</p>

## स्टार हिस्ट्री

<p align="center">
  <a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
    </picture>
  </a>
</p>

## लाइसेंस

Apache-2.0। देखें [LICENSE](LICENSE)।
