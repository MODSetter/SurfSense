<!--
  ملاحظة الإيقاف محدودة بزمن: تُحذف في 18 أكتوبر 2026، ومعها الملاحظة نفسها في README.md.
  هذا الملف يتابع README.md قسمًا بقسم.
  المسوغ: plans/community-local/seo/06-repo-readme.md
-->

<div align="center">

[![Stars](https://img.shields.io/github/stars/MODSetter/SurfSense?style=social)](https://github.com/MODSetter/SurfSense/stargazers)
[![Latest release](https://img.shields.io/github/v/release/MODSetter/SurfSense?sort=semver)](https://github.com/MODSetter/SurfSense/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Discord](https://img.shields.io/discord/1359368468260192417?label=Discord)](https://discord.gg/ejRNvftDp9)

  <a href="https://www.surfsense.com/"><img alt="SurfSense، بديل NotebookLM المعزول عن الشبكة والمفتوح المصدر" src="surfsense_web/public/homepage/banner.png" /></a>

  <h1>SurfSense</h1>

  <p>
    <b>بديل NotebookLM المعزول عن الشبكة والمفتوح المصدر.</b>
    <br />
    وكيل الذكاء الاصطناعي الذي يبحث في المستندات ويحوّلها ويحرّرها، على الجهاز نفسه.
  </p>

  <p>
    <a href="https://www.surfsense.com/downloads"><b>تنزيل</b></a> ·
    <a href="#ما-يفعله-بكل-صيغة">الصيغ</a> ·
    <a href="#بداية-سريعة">بداية سريعة</a> ·
    <a href="#كيف-يقارن-بغيره">المقارنة</a> ·
    <a href="https://www.surfsense.com/pricing">الأسعار</a> ·
    <a href="https://discord.gg/ejRNvftDp9">Discord</a>
  </p>

  <a href="https://trendshift.io/repositories/13606" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13606" alt="MODSetter/SurfSense | Trendshift" width="250" height="55" /></a>

  <p>
    <a href="README.md">English</a> | العربية | <a href="README.de.md">Deutsch</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.ja.md">日本語</a> | <a href="README.ko.md">한국어</a> | <a href="README.pt-BR.md">Português</a> | <a href="README.ru.md">Русский</a> | <a href="README.zh-CN.md">简体中文</a>
  </p>
</div>

https://github.com/user-attachments/assets/88326b9d-e763-46db-9635-75f9df9e8682

يُعد SurfSense تطبيق سطح مكتب مجانيًا ومفتوح المصدر للمستندات التي لا يمكن رفعها. وهو وكيل ذكاء اصطناعي يركّز على الخصوصية، على طريقة NotebookLM، يبحث في المستندات ويحوّلها ويحرّرها على الجهاز نفسه. يبقى الفهرس على القرص، ويُختار النموذج بحسب الرغبة، محليًا كان أو بعيدًا، ولا حساب أصلًا.

| المنصة | التنزيل |
|---|---|
| **Windows** x64 | [SurfSense-Setup.exe](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-Setup.exe) |
| **macOS** Apple Silicon | [SurfSense-arm64.dmg](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense-arm64.dmg) |
| **Linux** x64 | [AppImage](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.AppImage) · [deb](https://github.com/MODSetter/SurfSense/releases/latest/download/SurfSense.deb) |

> [!NOTE]
> **هل استُخدم تطبيق الويب المستضاف؟** تُصدَّر مساحات العمل قبل 18 أكتوبر 2026، ثم تُستورد هنا. التفاصيل في [صفحة الإيقاف](https://www.surfsense.com/sunset).

## بداية سريعة

1. تثبيت SurfSense وإتمام الإعداد الأولي (Start setting up).
2. إفلات الملفات أو المجلدات في المصادر (Sources).
3. تكليف الوكيل بالبحث في الملفات أو الاستخراج منها أو تحريرها.

## ما يفعله بكل صيغة

| الصيغة | البحث (إجابات مع ذكر المصدر) | الإنشاء | التحرير (على نسخة) | التحويل |
|---|---|---|---|---|
| **PDF** | ✓ والصفحات الممسوحة ضوئيًا أيضًا³ | ✓ | ملء النماذج وتسطيحها؛ وختم العلامات المائية وأرقام الصفحات ورؤوسها وتذييلاتها | دمج الصفحات وتقسيمها واستخراجها وتدويرها وإعادة ترتيبها |
| **Word** `.docx` | ✓ | ✓ أو انطلاقًا من ملف `.docx` خاص يُعتمد قالبًا | ✓ نص المتن، في صورة تغييرات متعقَّبة وتعليقات | إلى PDF¹ |
| **Excel** `.xlsx` | ✓ ويقرأ الوكيل الصيغ الحسابية أيضًا | ✓ مع صيغ حسابية ومخططات أصلية | ✓ قيم الخلايا والصيغ الحسابية | التحليل باستخدام pandas وتمثيل النتائج بمخططات |
| **PowerPoint** `.pptx` | ✓ | ✓ أو انطلاقًا من ملف `.pptx` خاص يُعتمد قالبًا | استبدال النص في الشرائح والملاحظات؛ وحذف الشرائح أو تكرارها | إلى PDF¹ |
| **CSV** | ✓ | — | — | التحليل باستخدام pandas وتمثيل النتائج بمخططات |
| **الصور** PNG, JPEG, TIFF, BMP, WebP | ✓ يُقرأ نصها بالتعرّف الضوئي على الحروف (OCR)³ | صور وإنفوجرافيك (Infographic)² | — | إدراجها في مستندات جديدة |
| **Markdown**، والنص العادي | ✓ | ✓ Markdown | — | — |
| **HTML** | ✓ | ✓ صفحة ويب | — | — |
| **بودكاست صوتي** (Podcast) | — | ✓ مع تفريغ نصي، وتُولَّد الأصوات على الجهاز نفسه افتراضيًا | — | — |
| **الخرائط الذهنية (Mind map)، والبطاقات التعليمية (Flashcards)، والاختبارات (Quiz)** | — | ✓ داخل التطبيق | — | — |

<sub>¹ مع دعم Office (Office support)، أي LibreOffice، الذي يُفعَّل من الإعدادات (Settings)؛ ولا يأتي ضمن برنامج التثبيت أبدًا. ² يتطلب نموذج صور، محليًا أو بعيدًا؛ ولا يُختار أي نموذج افتراضيًا. ³ يقرأ OCR النصوص المكتوبة بالحروف اللاتينية والصينية واليابانية.</sub>

عمليات التحرير والتحويل وأدوات PDF تُنشئ دائمًا ملفًا جديدًا، ولا يتغيّر الملف الأصلي أبدًا. تحظى ملفات PDF وWord وExcel اليوم بأوسع الإمكانات، ويتحسّن دعم الصيغ الأخرى باستمرار.

## كيف يقارن بغيره

| | NotebookLM (أصبح الآن Gemini Notebook) | SurfSense |
|---|---|---|
| يعمل بلا اتصال / معزولًا عن الشبكة | لا | **نعم** |
| المستندات تغادر الجهاز | نعم | **لا**، ما لم يُختر نموذج بعيد |
| يستطيع تحرير الملفات | لا | **نعم** |
| مفتوح المصدر | لا | **Apache-2.0** |
| النماذج | Gemini فقط | أي API متوافقة مع OpenAI، أو نموذج محلي |

## المجتمع

- المساعدة على [Discord](https://discord.gg/ejRNvftDp9)، والأعطال في [Issues](https://github.com/MODSetter/SurfSense/issues)، والأفكار في [Discussions](https://github.com/MODSetter/SurfSense/discussions).
- **المساهمة:** تُفتح طلبات السحب على الفرع `dev`، وحلقة التطوير مشروحة في [CONTRIBUTING.md](CONTRIBUTING.md) و[`surfsense_local/`](./surfsense_local). أما طريقة عمل التطبيق ففي [`docs/`](docs/README.md).

<a href="https://github.com/MODSetter/SurfSense/graphs/contributors"><img src="https://contrib.rocks/image?repo=MODSetter/SurfSense" alt="المساهمون في SurfSense" /></a>

## تاريخ النجوم

<p align="center">
  <a href="https://www.star-history.com/#MODSetter/SurfSense&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
      <img alt="مخطط تاريخ النجوم" src="https://api.star-history.com/svg?repos=MODSetter/SurfSense&type=Date" />
    </picture>
  </a>
</p>

## الرخصة

مرخّص بموجب Apache-2.0. التفاصيل في [LICENSE](LICENSE).
