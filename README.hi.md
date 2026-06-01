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

NotebookLM वहाँ उपलब्ध सबसे अच्छे और सबसे उपयोगी AI प्लेटफ़ॉर्म में से एक है, लेकिन जब आप इसे नियमित रूप से उपयोग करना शुरू करते हैं तो आप इसकी सीमाओं को भी महसूस करते हैं जो कुछ और की चाह छोड़ती हैं।

1. एक notebook में जोड़े जा सकने वाले स्रोतों की मात्रा पर सीमाएं हैं।
2. आपके पास कितने notebooks हो सकते हैं इस पर सीमाएं हैं।
3. आपके पास ऐसे स्रोत नहीं हो सकते जो 500,000 शब्दों और 200MB से अधिक हों।
4. आप Google सेवाओं (LLMs, उपयोग मॉडल, आदि) में बंद हैं और उन्हें कॉन्फ़िगर करने का कोई विकल्प नहीं है।
5. सीमित बाहरी डेटा स्रोत और सेवा एकीकरण।
6. NotebookLM एजेंट विशेष रूप से केवल अध्ययन और शोध के लिए अनुकूलित है, लेकिन आप स्रोत डेटा के साथ और भी बहुत कुछ कर सकते हैं।
7. मल्टीप्लेयर सपोर्ट की कमी।

...और भी बहुत कुछ।

**SurfSense विशेष रूप से इन समस्याओं को हल करने के लिए बनाया गया है।** SurfSense आपको सक्षम बनाता है:

- **अपने डेटा प्रवाह को नियंत्रित करें** - अपने डेटा को निजी और सुरक्षित रखें।
- **कोई डेटा सीमा नहीं** - असीमित मात्रा में स्रोत और notebooks जोड़ें।
- **कोई विक्रेता लॉक-इन नहीं** - किसी भी LLM, इमेज, TTS और STT मॉडल को कॉन्फ़िगर करें।
- **25+ बाहरी डेटा स्रोत** - Google Drive, OneDrive, Dropbox, Notion और कई अन्य बाहरी सेवाओं से अपने स्रोत जोड़ें।
- **रीयल-टाइम मल्टीप्लेयर सपोर्ट** - एक साझा notebook में अपनी टीम के सदस्यों के साथ आसानी से काम करें।
- **AI ऑटोमेशन और एजेंट** - AI एजेंट को शेड्यूल पर चलाएं या जैसे ही कोई दस्तावेज़ किसी फ़ोल्डर में आए उसे ट्रिगर करें, फिर परिणाम वापस Notion, Slack, Linear और Drive में लिखें। चैट में बस वर्णन करके बिना-कोड ऑटोमेशन बनाएं।
- **डेस्कटॉप ऐप** - Quick Assist, General Assist, Screenshot Assist और लोकल फ़ोल्डर सिंक के साथ किसी भी एप्लिकेशन में AI सहायता प्राप्त करें।

...और भी बहुत कुछ आने वाला है।



## वीडियो एजेंट नमूना

https://github.com/user-attachments/assets/012a7ffa-6f76-4f06-9dda-7632b470057a



## पॉडकास्ट एजेंट नमूना

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7


## SurfSense का उपयोग कैसे करें

### Cloud

1. [surfsense.com](https://www.surfsense.com) पर जाएं और लॉगिन करें।

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/LoginFlowGif.gif" alt="लॉगिन" /></p>

2. अपने कनेक्टर जोड़ें और सिंक करें। कनेक्टर्स को अपडेट रखने के लिए आवधिक सिंकिंग सक्षम करें।

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ConnectorFlowGif.gif" alt="कनेक्टर्स" /></p>

3. जब तक कनेक्टर्स का डेटा इंडेक्स हो रहा है, दस्तावेज़ अपलोड करें।

<p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/DocUploadGif.gif" alt="दस्तावेज़ अपलोड करें" /></p>

4. सब कुछ इंडेक्स हो जाने के बाद, कुछ भी पूछें (उपयोग के मामले):

   **डेस्कटॉप ऐप** (नीचे दी गई सभी सुविधाओं के अलावा नेटिव एक्स्ट्रा, कोई अलग सेट नहीं)

   - General Assist: किसी भी ऐप्लिकेशन से ग्लोबल शॉर्टकट के ज़रिए SurfSense तुरंत खोलें।

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/general_assist.gif" alt="General Assist" /></p>

   - Quick Assist: कहीं भी टेक्स्ट चुनें और AI से उसे समझाने, दोबारा लिखने या उस पर कार्रवाई करने को कहें।

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/quick_assist.gif" alt="Quick Assist" /></p>

   - Screenshot Assist: अपनी स्क्रीन का कोई भी हिस्सा कैप्चर करें और AI से उसमें मौजूद चीज़ों के बारे में पूछें।

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/screenshot_assist.gif" alt="Screenshot Assist" /></p>

   - Watch Local Folder: किसी लोकल फ़ोल्डर को अपने नॉलेज बेस के साथ अपने-आप सिंक करें। Obsidian vaults के लिए बढ़िया।

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/folder_watch.gif" alt="Watch Local Folder" /></p>

   **डिलीवरेबल स्टूडियो**

   - AI Report Generator: उद्धरण सहित रिसर्च रिपोर्ट बनाएं और PDF, DOCX, HTML, LaTeX, EPUB, ODT या सादे टेक्स्ट में एक्सपोर्ट करें।

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ReportGenGif_compressed.gif" alt="AI Report Generator" /></p>

   - AI Podcast Generator: किसी भी दस्तावेज़ या फ़ोल्डर को 20 सेकंड से भी कम में दो-होस्ट वाले AI पॉडकास्ट में बदलें।

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/PodcastGenGif.gif" alt="AI Podcast Generator" /></p>

   - AI Presentation & Video Maker: अपने स्रोतों से एडिट करने योग्य स्लाइड डेक और नैरेटेड वीडियो बनाएं।

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/video_gen_gif.gif" alt="AI Presentation and Video Maker" /></p>

   - AI Image Generator: अपनी चैट और दस्तावेज़ों से सीधे उच्च-गुणवत्ता वाली इमेज बनाएं।

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ImageGenGif.gif" alt="AI Image Generator" /></p>

   - AI Resume Builder: अपने मौजूदा रिज़्यूमे को किसी भी जॉब डिस्क्रिप्शन के अनुसार ढालें और ATS को पार करें।
     इस तरह के प्रॉम्प्ट आज़माएं:

     - "मेरे रिज़्यूमे को इस जॉब डिस्क्रिप्शन के अनुसार ढालें ताकि वह ATS पार करे और इंटरव्यू दिलाए।"
     - "इस जॉब पोस्टिंग के कीवर्ड्स से मिलान करके मेरे रिज़्यूमे को ATS के लिए ऑप्टिमाइज़ करें।"
     - "इस भूमिका के लिए ज़रूरी स्किल्स को उभारने के लिए मेरे रिज़्यूमे के बुलेट पॉइंट फिर से लिखें।"
     - "मेरे रिज़्यूमे की तुलना इस जॉब डिस्क्रिप्शन से करें और सुधारने योग्य कमियों की सूची दें।"
     - "मेरे रिज़्यूमे और इस जॉब डिस्क्रिप्शन से मेल खाता एक कवर लेटर लिखें।"

   **सर्च और चैट**

   - Chat With Your PDFs & Docs: अपनी सभी फ़ाइलों पर सवाल पूछें और इनलाइन उद्धरणों के साथ जवाब पाएं।

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BQnaGif_compressed.gif" alt="Chat With Your PDFs and Docs" /></p>

   - AI Search With Citations: अपने पूरे नॉलेज बेस में हाइब्रिड सेमांटिक और कीवर्ड सर्च।

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/BSNCGif.gif" alt="AI Search With Citations" /></p>

   - Collaborative AI Chat: अपनी टीम के साथ रियल टाइम में AI बातचीत पर काम करें।

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeChatGif.gif" alt="Collaborative AI Chat" /></p>

   - Comments & Mentions: किसी भी AI संदेश पर टिप्पणी करें और टीम के साथियों को टैग करें।

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeCommentsFlow.gif" alt="Comments and Mentions" /></p>

   **कनेक्टर्स और इंटीग्रेशन**

   - Connect & Sync Your Tools: Notion, Slack, Google Drive, Gmail, GitHub, Linear और 25+ स्रोतों को एक खोजने योग्य कॉर्पस में सिंक करें।

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/ConnectorFlowGif.gif" alt="Connect and Sync Your Tools" /></p>

   - Chat With Uploaded Files: PDF, Office दस्तावेज़, इमेज और ऑडियो अपलोड करें। तुरंत खोजने योग्य।

   <p align="center"><img src="surfsense_web/public/homepage/hero_tutorial/DocUploadGif.gif" alt="Chat With Uploaded Files" /></p>

   - Connector Write-Back: एजेंट को परिणाम वापस Notion, Slack, Linear और Drive में पोस्ट करने दें।
     इस तरह के प्रॉम्प्ट आज़माएं:

     - "इस रिसर्च सारांश को मेरे Notion वर्कस्पेस में पोस्ट करें।"
     - "इन मीटिंग एक्शन आइटम्स को हमारे टीम Slack चैनल पर भेजें।"
     - "इस बग रिपोर्ट से एक Jira टिकट बनाएं।"
     - "इस फ़ीचर अनुरोध से Linear में एक इश्यू खोलें।"
     - "इस जनरेट की गई रिपोर्ट को Google Drive में एक डॉक के रूप में सेव करें।"

   - Obsidian & Knowledge Base Sync: अपने Obsidian vault और व्यक्तिगत नॉलेज बेस को सिंक रखें।

   **ऑटोमेशन**

   - Scheduled AI Workflows: किसी एजेंट को शेड्यूल पर चलाएं: रोज़ाना ब्रीफ़, साप्ताहिक डाइजेस्ट, आवर्ती रिपोर्ट।
     इस तरह के प्रॉम्प्ट आज़माएं:

     - "हर सुबह मेरे नॉलेज बेस में जुड़े नए दस्तावेज़ों का रोज़ाना ब्रीफ़ मुझे ईमेल करें।"
     - "हर शुक्रवार मेरे Slack और Gmail से एक साप्ताहिक स्टेटस रिपोर्ट बनाएं।"
     - "एक मासिक प्रतिस्पर्धी विश्लेषण रिपोर्ट चलाएं और उसे मेरे वर्कस्पेस में सेव करें।"
     - "मेरी GitHub और Linear गतिविधि को एक रोज़ाना standup अपडेट में सारांशित करें।"
     - "मैं जिन विषयों को ट्रैक करता हूं उन पर एक आवर्ती साप्ताहिक रिसर्च रिपोर्ट बनाएं।"

   - Event-Triggered Automations: जैसे ही कोई दस्तावेज़ किसी फ़ोल्डर में आता है, एजेंट को चलाएं और परिणाम अपने टूल में पोस्ट करें।
     इस तरह के प्रॉम्प्ट आज़माएं:

     - "जब मेरे Research फ़ोल्डर में कोई PDF आए, तो उद्धरण सहित एक AI सारांश बनाएं।"
     - "जब नई मीटिंग नोट्स जुड़ें, तो उन्हें एक्शन आइटम्स के साथ मीटिंग मिनट्स में बदलें।"
     - "जब कोई इनवॉइस अपलोड हो, तो विक्रेता, कुल राशि और देय तिथि को एक तालिका में निकालें।"
     - "जब मेरे Legal फ़ोल्डर में कोई अनुबंध आए, तो मुख्य शर्तों और नवीनीकरण तिथियों को चिह्नित करें।"
     - "जब Candidates में कोई रिज़्यूमे जुड़े, तो उसे जॉब डिस्क्रिप्शन के विरुद्ध स्क्रीन करें।"

   - Chat-Built Automations: सरल भाषा में किसी ऑटोमेशन का वर्णन करें और SurfSense उसे आपके लिए बना देगा।
     इस तरह के प्रॉम्प्ट आज़माएं:

     - "एक AI एजेंट बनाएं जो हर सुबह नई Notion पेजों का सारांश मुझे ईमेल करे।"
     - "एक नो-कोड ऑटोमेशन बनाएं जो हर सप्ताह एक रिसर्च डाइजेस्ट Slack पर पोस्ट करे।"
     - "एक AI नोट-टेकर सेट करें जो नई मीटिंग नोट्स को मिनट्स में बदल दे।"
     - "एक वर्कफ़्लो बनाएं जो मीटिंग नोट्स से एक्शन आइटम्स निकाले और ज़िम्मेदार सौंपे।"
     - "मेरे Gmail और Google Drive से एक रोज़ाना ईमेल ब्रीफ़ को ऑटोमेट करें।"


### सेल्फ-होस्टेड

पूर्ण डेटा नियंत्रण और गोपनीयता के लिए SurfSense को अपने स्वयं के बुनियादी ढांचे पर चलाएं।

**आवश्यकताएँ:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) इंस्टॉल और चालू होना चाहिए।

#### Linux/MacOS उपयोगकर्ताओं के लिए:

```bash
curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.sh | bash
```

#### Windows उपयोगकर्ताओं के लिए:

```powershell
irm https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.ps1 | iex
```

इंस्टॉल स्क्रिप्ट दैनिक ऑटो-अपडेट के लिए स्वचालित रूप से [Watchtower](https://github.com/nicholas-fedor/watchtower) सेटअप करती है। इसे छोड़ने के लिए, `--no-watchtower` फ्लैग जोड़ें।

Docker Compose, मैनुअल इंस्टॉलेशन और अन्य डिप्लॉयमेंट विकल्पों के लिए, [डॉक्स](https://www.surfsense.com/docs/) देखें।

### डेस्कटॉप ऐप

SurfSense एक डेस्कटॉप ऐप भी प्रदान करता है जो आपके कंप्यूटर पर हर एप्लिकेशन में AI सहायता लाता है। इसे [नवीनतम रिलीज़](https://github.com/MODSetter/SurfSense/releases/latest) से डाउनलोड करें।

डेस्कटॉप ऐप में ये शक्तिशाली सुविधाएं शामिल हैं:

- **General Assist** — एक ग्लोबल शॉर्टकट से किसी भी एप्लिकेशन से तुरंत SurfSense लॉन्च करें।
- **Quick Assist** — कहीं भी टेक्स्ट चुनें, फिर AI से समझाने, फिर से लिखने या उस पर कार्रवाई करने को कहें।
- **Screenshot Assist** — स्क्रीन पर एक क्षेत्र चुनें और उसे चैट में जोड़ें, ताकि उत्तर आपकी नॉलेज बेस पर आधारित रहें।
- **Watch Local Folder** — एक लोकल फ़ोल्डर को वॉच करें और फ़ाइल परिवर्तनों को स्वचालित रूप से अपनी नॉलेज बेस में सिंक करें। **Pro tip:** इसे अपने Obsidian vault पर पॉइंट करें ताकि आपके नोट्स SurfSense में सर्च करने योग्य रहें।

सभी सुविधाएं आपके चुने हुए सर्च स्पेस पर काम करती हैं, ताकि आपके उत्तर हमेशा आपके अपने डेटा पर आधारित हों।

### रीयल-टाइम सहयोग कैसे करें (बीटा)

1. सदस्य प्रबंधन पेज पर जाएं और एक आमंत्रण बनाएं।

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="सदस्यों को आमंत्रित करें" /></p>

2. टीममेट जुड़ता है और वह SearchSpace साझा हो जाता है।

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="आमंत्रण स्वीकार प्रवाह" /></p>

3. चैट को साझा करें।

   <p align="center"><img src="https://github.com/user-attachments/assets/17b93904-0888-4c3a-ac12-51a24a8ea26a" alt="चैट साझा करें" /></p>

4. आपकी टीम अब रीयल-टाइम में चैट कर सकती है।

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeChatGif.gif" alt="रीयल-टाइम चैट" /></p>

5. टीममेट्स को टैग करने के लिए कमेंट जोड़ें।

   <p align="center"><img src="surfsense_web/public/homepage/hero_realtime/RealTimeCommentsFlow.gif" alt="रीयल-टाइम कमेंट्स" /></p>

## SurfSense vs Google NotebookLM

| विशेषता | Google NotebookLM | SurfSense |
|---------|-------------------|-----------|
| **प्रति Notebook स्रोत** | 50 (मुफ़्त) से 600 (Ultra, $249.99/माह) | असीमित |
| **Notebooks की संख्या** | 100 (मुफ़्त) से 500 (सशुल्क योजनाएं) | असीमित |
| **स्रोत आकार सीमा** | 500,000 शब्द / 200MB प्रति स्रोत | कोई सीमा नहीं |
| **मूल्य निर्धारण** | मुफ़्त स्तर उपलब्ध; Pro $19.99/माह, Ultra $249.99/माह | मुफ़्त और ओपन सोर्स, अपनी इंफ्रा पर सेल्फ-होस्ट करें |
| **LLM सपोर्ट** | केवल Google Gemini | 100+ LLMs OpenAI spec और LiteLLM के माध्यम से |
| **एम्बेडिंग मॉडल** | केवल Google | 6,000+ एम्बेडिंग मॉडल, सभी प्रमुख रीरैंकर्स |
| **लोकल / प्राइवेट LLMs** | उपलब्ध नहीं | पूर्ण सपोर्ट (vLLM, Ollama) - आपका डेटा आपका रहता है |
| **सेल्फ-होस्ट करने योग्य** | नहीं | हाँ - Docker एक कमांड या पूर्ण Docker Compose |
| **ओपन सोर्स** | नहीं | हाँ |
| **बाहरी कनेक्टर्स** | Google Drive, YouTube, वेबसाइटें | 27+ कनेक्टर्स - सर्च इंजन, Google Drive, OneDrive, Dropbox, Slack, Teams, Jira, Notion, GitHub, Discord और [अधिक](#बाहरी-स्रोत) |
| **फ़ाइल फ़ॉर्मेट सपोर्ट** | PDFs, Docs, Slides, Sheets, CSV, Word, EPUB, इमेज, वेब URLs, YouTube | 50+ फ़ॉर्मेट - दस्तावेज़, इमेज, वीडियो LlamaCloud, Unstructured या Docling (लोकल) के माध्यम से |
| **सर्च** | सिमैंटिक सर्च | हाइब्रिड सर्च - हायरार्किकल इंडाइसेस और Reciprocal Rank Fusion के साथ सिमैंटिक + फुल टेक्स्ट |
| **उद्धृत उत्तर** | हाँ | हाँ - Perplexity शैली के उद्धृत उत्तर |
| **एजेंट आर्किटेक्चर** | नहीं | हाँ - [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) द्वारा संचालित, योजना, सब-एजेंट और फ़ाइल सिस्टम एक्सेस |
| **रीयल-टाइम मल्टीप्लेयर** | दर्शक/संपादक भूमिकाओं के साथ साझा notebooks (कोई रीयल-टाइम चैट नहीं) | मालिक / एडमिन / संपादक / दर्शक भूमिकाओं के साथ RBAC, रीयल-टाइम चैट और कमेंट थ्रेड |
| **वीडियो जनरेशन** | Veo 3 के माध्यम से सिनेमैटिक वीडियो ओवरव्यू (केवल Ultra) | उपलब्ध (NotebookLM यहाँ बेहतर है, सक्रिय रूप से सुधार हो रहा है) |
| **प्रेजेंटेशन जनरेशन** | बेहतर दिखने वाली स्लाइड्स लेकिन संपादन योग्य नहीं | संपादन योग्य, स्लाइड आधारित प्रेजेंटेशन बनाएं |
| **पॉडकास्ट जनरेशन** | कस्टमाइज़ेबल होस्ट और भाषाओं के साथ ऑडियो ओवरव्यू | कई TTS प्रदाताओं के साथ उपलब्ध (NotebookLM यहाँ बेहतर है, सक्रिय रूप से सुधार हो रहा है) |
| **AI ऑटोमेशन और एजेंट** | नहीं | शेड्यूल किए गए AI वर्कफ़्लो, नए दस्तावेज़ों पर इवेंट ट्रिगर, और चैट से बने बिना-कोड ऑटोमेशन, Notion, Slack, Linear और Jira में कनेक्टर राइट-बैक के साथ |
| **डेस्कटॉप ऐप** | नहीं | General Assist, Quick Assist, Screenshot Assist और लोकल फ़ोल्डर सिंक के साथ नेटिव ऐप |
| **ब्राउज़र एक्सटेंशन** | नहीं | किसी भी वेबपेज को सहेजने के लिए क्रॉस-ब्राउज़र एक्सटेंशन, प्रमाणीकरण सुरक्षित पेज सहित |

<details>
<summary><b>बाहरी स्रोतों की पूरी सूची</b></summary>
<a id="बाहरी-स्रोत"></a>

सर्च इंजन (SearXNG, Tavily, LinkUp, Baidu Search) · Google Drive · OneDrive · Dropbox · Slack · Microsoft Teams · Linear · Jira · ClickUp · Confluence · BookStack · Notion · Gmail · YouTube वीडियो · GitHub · Discord · Airtable · Google Calendar · Luma · Circleback · Elasticsearch · Obsidian, और भी बहुत कुछ आने वाला है।

</details>


## फ़ीचर अनुरोध और भविष्य


**SurfSense सक्रिय रूप से विकसित किया जा रहा है।** हालांकि यह अभी प्रोडक्शन-रेडी नहीं है, आप प्रक्रिया को तेज़ करने में हमारी मदद कर सकते हैं।

[SurfSense Discord](https://discord.gg/ejRNvftDp9) में शामिल हों और SurfSense के भविष्य को आकार देने में मदद करें!

## रोडमैप

हमारे विकास की प्रगति और आने वाली सुविधाओं से अपडेट रहें!  
हमारा सार्वजनिक रोडमैप देखें और अपने विचार या फ़ीडबैक दें:

**रोडमैप चर्चा:** [SurfSense 2026 Roadmap](https://github.com/MODSetter/SurfSense/discussions/565)

**कानबन बोर्ड:** [SurfSense Project Board](https://github.com/users/MODSetter/projects/3)


## योगदान करें

सभी योगदान स्वागत योग्य हैं, स्टार और बग रिपोर्ट से लेकर बैकएंड सुधार तक। शुरू करने के लिए [CONTRIBUTING.md](CONTRIBUTING.md) देखें।

हमारे सभी Surfers को धन्यवाद:

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" />
</a>

## Star इतिहास

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
