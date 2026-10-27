<!--
  सनसेट कॉलआउट समय-सीमित है: इसे 18 अक्टूबर 2026 को README.md के उसी कॉलआउट के साथ हटा दें।
  यह फ़ाइल README.md को सेक्शन-दर-सेक्शन फ़ॉलो करती है।
  तर्क: plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img alt="SurfSense, एयर-गैप्ड, ओपन-सोर्स NotebookLM विकल्प" src="www/public/homepage/banner.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>एयर-गैप्ड, ओपन-सोर्स NotebookLM विकल्प।</b>
    <br />
    वह AI एजेंट जो आपके दस्तावेज़ों पर रिसर्च करता है, उन्हें ट्रांसफ़ॉर्म और एडिट करता है — आपकी अपनी मशीन पर।
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>डाउनलोड</b></a> ·
    <a href="#हर-फ़ॉर्मैट-के-साथ-यह-क्या-करता-है">फ़ॉर्मैट</a> ·
    <a href="#झटपट-शुरुआत">झटपट शुरुआत</a> ·
    <a href="#दूसरों-से-तुलना">तुलना</a> ·
    <a href="#प्लगइन">प्लगइन</a> ·
    <a href="https://www.surfsense.com/pricing">प्राइसिंग</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | <a href="README.ar.md">العربية</a> | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | हिन्दी | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

**ट्रैक किए गए बदलावों और टिप्पणियों के साथ अनुबंध रेडलाइन करें**

https://github.com/user-attachments/assets/88326b9d-e763-46db-9635-75f9df9e8682

**वेब से स्रोत जोड़ें, फिर उनसे एक वेब पेज बनाएं**

https://github.com/user-attachments/assets/073577b7-f055-4f59-8540-330bd764aeb0

SurfSense एक मुफ़्त, ओपन-सोर्स डेस्कटॉप ऐप है, उन दस्तावेज़ों के लिए जिन्हें आप अपलोड नहीं कर सकते। यह प्राइवेसी को केंद्र में रखकर बना, NotebookLM जैसा AI एजेंट है, जो आपके दस्तावेज़ों पर रिसर्च करता है, उन्हें ट्रांसफ़ॉर्म और एडिट करता है, और यह सब आपकी अपनी मशीन पर। इंडेक्स आपकी डिस्क पर रहता है, मॉडल आप चुनते हैं, चाहे लोकल हो या रिमोट, और कोई अकाउंट नहीं है।

| प्लैटफ़ॉर्म | डाउनलोड |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://www.surfsense.com/downloads/windows?src=readme) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://www.surfsense.com/downloads/mac?src=readme) |
| **Linux** x64 | [AppImage](https://www.surfsense.com/downloads/linux-appimage?src=readme) · [deb](https://www.surfsense.com/downloads/linux-deb?src=readme) |

## झटपट शुरुआत

1. SurfSense इंस्टॉल करें और शुरुआती सेटअप पूरा करें।
2. अपनी फ़ाइलें या फ़ोल्डर अपने स्रोतों में छोड़ें।
3. एजेंट से कहें कि वह आपकी फ़ाइलों में खोजे, उनसे जानकारी निकाले या उन्हें एडिट करे।

## हर फ़ॉर्मैट के साथ यह क्या करता है

| फ़ॉर्मैट | रिसर्च (हवालों के साथ जवाब) | बनाना | एडिट (कॉपी के रूप में) | ट्रांसफ़ॉर्म |
|---|---|---|---|---|
| **PDF** | ✓ स्कैन किए गए पेज भी³ | ✓ | फ़ॉर्म भरना और फ़्लैटन करना; वॉटरमार्क, पेज नंबर, हेडर, फ़ुटर लगाना | पेज मर्ज करना, अलग करना, निकालना, घुमाना, उनका क्रम बदलना |
| **Word** `.docx` | ✓ | ✓ या अपनी `.docx` को टेम्प्लेट बनाकर | ✓ बॉडी टेक्स्ट, ट्रैक किए गए बदलावों और टिप्पणियों के रूप में | PDF में¹ |
| **Excel** `.xlsx` | ✓ एजेंट फ़ॉर्मूले भी पढ़ता है | ✓ फ़ॉर्मूलों और नेटिव चार्ट के साथ | ✓ सेल की वैल्यू और फ़ॉर्मूले | pandas से विश्लेषण करना, नतीजों का चार्ट बनाना |
| **PowerPoint** `.pptx` | ✓ | ✓ या अपनी `.pptx` को टेम्प्लेट बनाकर | स्लाइड और नोट्स का टेक्स्ट बदलना; स्लाइड हटाना या डुप्लिकेट करना | PDF में¹ |
| **CSV** | ✓ | — | — | pandas से विश्लेषण करना, नतीजों का चार्ट बनाना |
| **इमेज** PNG, JPEG, TIFF, BMP, WebP | ✓ टेक्स्ट OCR से पढ़ा जाता है³ | इमेज और इन्फ़ोग्राफ़िक² | — | नए दस्तावेज़ों में लगाना |
| **Markdown**, सादा टेक्स्ट | ✓ | ✓ Markdown | — | — |
| **HTML** | ✓ | ✓ वेब पेज | — | — |
| **रिकॉर्डिंग** WAV, MP3, FLAC, Ogg Vorbis | ✓ आपकी अपनी मशीन पर ट्रांसक्राइब की जाती हैं | — | — | — |
| **पॉडकास्ट** (ऑडियो) | — | ✓ ट्रांसक्रिप्ट के साथ, आवाज़ डिफ़ॉल्ट रूप से आपकी अपनी मशीन पर दी जाती है | — | — |
| **माइंड मैप, फ़्लैशकार्ड, क्विज़** | — | ✓ ऐप के अंदर | — | — |

<sub>¹ Office सपोर्ट (LibreOffice) के साथ, जिसे सेटिंग्स में चालू किया जाता है; यह इंस्टॉलर में कभी शामिल नहीं होता। ² इमेज मॉडल चाहिए, लोकल या रिमोट; डिफ़ॉल्ट रूप से कोई भी मॉडल चुना हुआ नहीं होता। ³ OCR लैटिन, चीनी और जापानी लिपि पढ़ता है।</sub>

एडिट, कन्वर्ज़न और PDF टूल हमेशा एक नई फ़ाइल बनाते हैं; आपकी मूल फ़ाइल कभी नहीं बदली जाती। आज सबसे ज़्यादा सुविधाएँ PDF, Word और Excel के लिए हैं, और बाकी फ़ॉर्मैट का सपोर्ट लगातार बेहतर हो रहा है।

## प्लगइन

इन्हें **सेटिंग्स › प्लगइन** में कनेक्ट करें।

**SurfSense की ओर से।** ये आपके अपने अकाउंट के बिना सार्वजनिक पेज पढ़ते हैं और इनके लिए SurfSense लाइसेंस ज़रूरी है: [ऐप डाउनलोड करें](https://www.surfsense.com/downloads) और 14 दिन का मुफ़्त लाइसेंस पाने के लिए वहाँ अपना ईमेल डालें।

| प्लगइन | यह क्या करता है |
|---|---|
| **Google Search** | Google पर खोजना और उसके नतीजे, विज्ञापन और संबंधित सवाल पढ़ना |
| **Web Crawl** | कोई वेब पेज पढ़ना, या पूरी साइट को क्रॉल करके साफ़ टेक्स्ट में बदलना |
| **YouTube** | YouTube के वीडियो, चैनल और उनकी टिप्पणियाँ पढ़ना |
| **TikTok** | TikTok के वीडियो और उनकी टिप्पणियाँ पढ़ना, यूज़र खोजना और यह देखना कि क्या ट्रेंड कर रहा है |
| **Reddit** | Reddit की सार्वजनिक पोस्ट उनकी टिप्पणियों के थ्रेड के साथ, या पूरी कम्युनिटी पढ़ना |
| **Instagram** | Instagram की सार्वजनिक प्रोफ़ाइल, पोस्ट और रील्स पढ़ना, और प्रोफ़ाइल खोजना |
| **Google Maps** | Google Maps पर जगहें खोजना और उनके रिव्यू पढ़ना |
| **Amazon** | Amazon के प्रोडक्ट और खोज के नतीजे पढ़ना |
| **Walmart** | Walmart के प्रोडक्ट, खोज के नतीजे और रिव्यू पढ़ना |
| **Indeed** | Indeed पर नौकरियों की लिस्टिंग पढ़ना |

**थर्ड-पार्टी।** [प्लगइन रजिस्ट्री](backend/plugins/registry) के MCP सर्वर, जैसे DeepWiki और Notion, या कोई भी सर्वर जिसे आप URL से जोड़ें। इनके लिए लाइसेंस की ज़रूरत नहीं; जब तक आप अनुमति न दें, ये बंद रहते हैं।

## दूसरों से तुलना

| | NotebookLM (अब Gemini Notebook) | SurfSense |
|---|---|---|
| ऑफ़लाइन / एयर-गैप्ड चलता है | नहीं | **हाँ** |
| आपके दस्तावेज़ आपकी मशीन से बाहर जाते हैं | हाँ | **नहीं**, जब तक आप कोई रिमोट मॉडल न चुनें |
| आपकी फ़ाइलें एडिट कर सकता है | नहीं | **हाँ** |
| ओपन सोर्स | नहीं | **Apache-2.0** |
| मॉडल | सिर्फ़ Gemini | कोई भी OpenAI-संगत API, या कोई लोकल मॉडल |

## कम्युनिटी

- मदद के लिए [Discord](https://discord.gg/ejRNvftDp9), बग के लिए [Issues](https://github.com/MODSetter/SurfSense/issues), और आइडिया के लिए [Discussions](https://github.com/MODSetter/SurfSense/discussions)।
- **योगदान:** PR `dev` ब्रांच पर खोलें; डेवलपमेंट लूप के लिए [CONTRIBUTING.md](CONTRIBUTING.md) और [`surfsense_local/`](./surfsense_local) देखें। यह कैसे काम करता है, यह [`docs/`](docs/README.md) में बताया गया है।

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors"><img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="SurfSense में योगदान देने वाले लोग" /></a>

## लाइसेंस

Apache-2.0। [LICENSE](LICENSE) देखें।
