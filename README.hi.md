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
किसी भी LLM को अपने आंतरिक ज्ञान स्रोतों से जोड़ें और अपनी टीम के साथ रीयल-टाइम में चैट करें। NotebookLM, Perplexity और Glean का ओपन सोर्स विकल्प।

SurfSense एक अत्यधिक अनुकूलन योग्य AI शोध एजेंट है, जो बाहरी स्रोतों से जुड़ा है जैसे सर्च इंजन (SearxNG, Tavily, LinkUp), Google Drive, Slack, Microsoft Teams, Linear, Jira, ClickUp, Confluence, BookStack, Gmail, Notion, YouTube, GitHub, Discord, Airtable, Google Calendar, Luma, Circleback, Elasticsearch, Obsidian और भी बहुत कुछ आने वाला है।



# वीडियो 

https://github.com/user-attachments/assets/cc0c84d3-1f2f-4f7a-b519-2ecce22310b1

## पॉडकास्ट नमूना

https://github.com/user-attachments/assets/a0a16566-6967-4374-ac51-9b3e07fbecd7


## SurfSense का उपयोग कैसे करें

### Cloud

1. [surfsense.com](https://www.surfsense.com) पर जाएं और लॉगिन करें।

<p align="center"><img src="https://github.com/user-attachments/assets/b4df25fe-db5a-43c2-9462-b75cf7f1b707" alt="लॉगिन" /></p>

2. अपने कनेक्टर जोड़ें और सिंक करें। कनेक्टर्स को अपडेट रखने के लिए आवधिक सिंकिंग सक्षम करें।

<p align="center"><img src="https://github.com/user-attachments/assets/59da61d7-da05-4576-b7c0-dbc09f5985e8" alt="कनेक्टर्स" /></p>

3. जब तक कनेक्टर्स का डेटा इंडेक्स हो रहा है, दस्तावेज़ अपलोड करें।

<p align="center"><img src="https://github.com/user-attachments/assets/d1e8b2e2-9eac-41d8-bdc0-f0cdc405d128" alt="दस्तावेज़ अपलोड करें" /></p>

4. सब कुछ इंडेक्स हो जाने के बाद, कुछ भी पूछें (उपयोग के मामले):

   - बेसिक सर्च और उद्धरण

   <p align="center"><img src="https://github.com/user-attachments/assets/81e797a1-e01a-4003-8e60-0a0b3a9789df" alt="सर्च और उद्धरण" /></p>

   - दस्तावेज़ मेंशन QNA

   <p align="center"><img src="https://github.com/user-attachments/assets/be958295-0a8c-4707-998c-9fe1f1c007be" alt="दस्तावेज़ मेंशन QNA" /></p>

   - रिपोर्ट जनरेशन और एक्सपोर्ट (फ़िलहाल PDF, DOCX)

   <p align="center"><img src="https://github.com/user-attachments/assets/9836b7d6-57c9-4951-b61c-68202c9b6ace" alt="रिपोर्ट जनरेशन" /></p>

   - पॉडकास्ट जनरेशन

   <p align="center"><img src="https://github.com/user-attachments/assets/58c9b057-8848-4e81-aaba-d2c617985d8c" alt="पॉडकास्ट जनरेशन" /></p>

   - इमेज जनरेशन

   <p align="center"><img src="https://github.com/user-attachments/assets/25f94cb3-18f8-4854-afd9-27b7bfd079cb" alt="इमेज जनरेशन" /></p>

   - और भी बहुत कुछ जल्द आ रहा है।


### सेल्फ-होस्टेड

पूर्ण डेटा नियंत्रण और गोपनीयता के लिए SurfSense को अपने स्वयं के बुनियादी ढांचे पर चलाएं।

**त्वरित शुरुआत (Docker एक कमांड में):**

```bash
docker run -d -p 3000:3000 -p 8000:8000 -p 5133:5133 -v surfsense-data:/data --name surfsense --restart unless-stopped ghcr.io/modsetter/surfsense:latest
```

शुरू करने के बाद, अपने ब्राउज़र में [http://localhost:3000](http://localhost:3000) खोलें।

Docker Compose, मैनुअल इंस्टॉलेशन और अन्य डिप्लॉयमेंट विकल्पों के लिए, [डॉक्स](https://www.surfsense.com/docs/) देखें।

### रीयल-टाइम सहयोग कैसे करें (बीटा)

1. सदस्य प्रबंधन पेज पर जाएं और एक आमंत्रण बनाएं।

   <p align="center"><img src="https://github.com/user-attachments/assets/40ed7683-5aa6-48a0-a3df-00575528c392" alt="सदस्यों को आमंत्रित करें" /></p>

2. टीममेट जुड़ता है और वह SearchSpace साझा हो जाता है।

   <p align="center"><img src="https://github.com/user-attachments/assets/ea4e1057-4d2b-4fd2-9ca0-cd19286a285e" alt="आमंत्रण स्वीकार प्रवाह" /></p>

3. चैट को साझा करें।

   <p align="center"><img src="https://github.com/user-attachments/assets/17b93904-0888-4c3a-ac12-51a24a8ea26a" alt="चैट साझा करें" /></p>

4. आपकी टीम अब रीयल-टाइम में चैट कर सकती है।

   <p align="center"><img src="https://github.com/user-attachments/assets/83803ac2-fbce-4d93-aae3-85eb85a3053a" alt="रीयल-टाइम चैट" /></p>

5. टीममेट्स को टैग करने के लिए कमेंट जोड़ें।

   <p align="center"><img src="https://github.com/user-attachments/assets/3b04477d-8f42-4baa-be95-867c1eaeba87" alt="रीयल-टाइम कमेंट्स" /></p>

## प्रमुख विशेषताएं

| विशेषता | विवरण |
|----------|--------|
| OSS विकल्प | रीयल-टाइम टीम सहयोग के साथ NotebookLM, Perplexity और Glean का सीधा प्रतिस्थापन |
| 50+ फ़ाइल फ़ॉर्मेट | LlamaCloud, Unstructured या Docling (लोकल) के माध्यम से दस्तावेज़, चित्र, वीडियो अपलोड करें |
| हाइब्रिड सर्च | हायरार्किकल इंडाइसेस और Reciprocal Rank Fusion के साथ सिमैंटिक + फुल टेक्स्ट सर्च |
| उद्धृत उत्तर | अपने ज्ञान आधार के साथ चैट करें और Perplexity शैली के उद्धृत उत्तर पाएं |
| डीप एजेंट आर्किटेक्चर | [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) द्वारा संचालित, योजना, सब-एजेंट और फ़ाइल सिस्टम एक्सेस |
| यूनिवर्सल LLM सपोर्ट | 100+ LLMs, 6000+ एम्बेडिंग मॉडल, सभी प्रमुख रीरैंकर्स OpenAI spec और LiteLLM के माध्यम से |
| प्राइवेसी फर्स्ट | पूर्ण लोकल LLM सपोर्ट (vLLM, Ollama) आपका डेटा आपका रहता है |
| टीम सहयोग | मालिक / एडमिन / संपादक / दर्शक भूमिकाओं के साथ RBAC, रीयल-टाइम चैट और कमेंट थ्रेड |
| पॉडकास्ट जनरेशन | 20 सेकंड से कम में 3 मिनट का पॉडकास्ट; कई TTS प्रदाता (OpenAI, Azure, Kokoro) |
| ब्राउज़र एक्सटेंशन | किसी भी वेबपेज को सहेजने के लिए क्रॉस-ब्राउज़र एक्सटेंशन, प्रमाणीकरण सुरक्षित पेज सहित |
| 25+ कनेक्टर्स | सर्च इंजन, Google Drive, Slack, Teams, Jira, Notion, GitHub, Discord और [अधिक](#बाहरी-स्रोत) |
| सेल्फ-होस्ट करने योग्य | ओपन सोर्स, Docker एक कमांड या प्रोडक्शन के लिए पूर्ण Docker Compose |

<details>
<summary><b>बाहरी स्रोतों की पूरी सूची</b></summary>
<a id="बाहरी-स्रोत"></a>

सर्च इंजन (Tavily, LinkUp) · SearxNG · Google Drive · Slack · Microsoft Teams · Linear · Jira · ClickUp · Confluence · BookStack · Notion · Gmail · YouTube वीडियो · GitHub · Discord · Airtable · Google Calendar · Luma · Circleback · Elasticsearch · Obsidian, और भी बहुत कुछ आने वाला है।

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
