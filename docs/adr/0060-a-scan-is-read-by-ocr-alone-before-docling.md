# ADR 0060: A scan or a photo is read by OCR alone, RapidOCR or Apple's Vision, and Docling reads only a page OCR could not

- **Status:** Accepted
- **Date:** 2026-10-17
- **Source:** measured on a Ryzen 7 5800X under Windows 11, on a GitHub macOS runner (a 3-core M1 virtual machine), and with Haiku 5.5 for answers; recorded in [documents](../architecture/documents.md#scans-and-photos)

## Context

A scanned PDF, a PDF page with no text layer and an uploaded image went to Docling with OCR and table structure on. On 499 real pages it took 4.9 s and 39 CPU-s a page, plus 8 to 17 s to import Docling and load its models in a worker's first job: a 20-page scan was ready in 98.5 s, and [ADR 0059](0059-a-born-digital-pdf-is-read-from-its-text-layer.md)'s text layer, which cut born-digital PDFs to seconds, could do nothing for it.

The pages were real, not rendered from born-digital files: 80 scanned business forms (FUNSD) and 80 DocVQA pages (letters, tables and reports from the UCSF Industry Documents Library, with 374 human questions and answers), 60 scanned receipts (SROIE) and 60 phone photos of receipts (CORD), 36 pages of three Internet Archive book scans with their Project Gutenberg text, one in French, 20 camera captures of printed pages (SmartDoc 2015), and six public scanned PDFs of 13 to 40 pages from the National Archives, govinfo and RECAP. Every reader was scored on the same pages, against human ground truth.

Docling's time on a scan went mostly to its layout model and TableFormer, not to OCR: RapidOCR, which Docling runs inside on each text region with the PP-OCRv6 small models, reads a whole page alone in about 2 s and 8 CPU-s. Read alone, it also found more of each page. Docling's layout step keeps only the text of the regions it classes, and drops running headers and page numbers outright: it kept 0.04 of the book scans' numbers, where RapidOCR alone kept 0.93.

| Real pages | RapidOCR alone | Docling | Windows OCR | Vision (accurate) |
|---|---|---|---|---|
| Words found, forms | 0.80 | 0.72 | 0.61 | 0.71 |
| Words found, receipt scans | 0.90 | 0.87 | 0.69 | 0.89 |
| Words found, receipt photos | 0.83 | 0.79 | 0.43 | 0.80 |
| Words found, books (English / French) | 0.98 / 0.92 | 0.97 / 0.90 | 0.98 / 0.83 | 0.99 / 0.92 |
| Words found, camera captures | 0.05 | 0.05 | 0.00 | 0.94 |
| Numbers found, all pages | 0.65 | 0.59 | 0.40 | 0.67 |
| DocVQA answers in the text | 0.88 | 0.70 | 0.70 | 0.86 |
| Seconds a page | 2.0 | 4.9 | 0.24 | 2.4 on the VM |

Answers followed: Haiku 5.5, given each page's text whole, answered 0.79 of the 374 DocVQA questions exactly from RapidOCR's text and 0.60 from Docling's Markdown, and 0.97 of 120 receipt totals and dates against 0.93. It replied that the text did not say for 34 questions against 104. Tables included: the DocVQA pages hold most of the corpus's tables, and RapidOCR's lines, ordered into rows, read them better than Docling's pipe tables.

## Decision

- **What OCR reads first.** A PDF's pages with no text layer, with a scanner's invisible OCR layer, with text pdfium cannot map, a turned page that is a scan, and, when no page is running text, its cover and picture pages; and every uploaded image. They are rendered greyscale at 216 dpi, an image as an A4 page as before, and read by the reader below. The code is [`scan_ocr/`](../../surfsense_local/backend/worker/ingestion/scan_ocr/) and [`pdf_reading/ocr_first.py`](../../surfsense_local/backend/worker/ingestion/pdf_reading/ocr_first.py).
- **The reader.** RapidOCR alone on Windows and Linux: the parser pack's own PP-OCRv6 small files, or the identical ones in the rapidocr wheel, with the line classifier off as Docling has it, 4 pages at a time at one onnxruntime thread each, which spends the least CPU a page. On a Mac, Apple's Vision at its accurate level, through PyObjC; RapidOCR if Vision cannot start. Vision's fast level found 0.27 of all words and is not used. Each reader's boxes are put in reading order the same way: a visual row reads left to right as one line, so a table's label and amount stay together, and two columns of prose read one after the other.
- **Which pages stand.** A page stands unless its OCR is garbled: mostly symbols, RapidOCR's own confidence under 0.8 (0.85 or more on every upright real page, 0.56 to 0.79 on sideways photos), or, for Vision, which gives none used here, under 30% of its characters in words of three letters. A page that looks read sideways, its text unsure or its lines standing on end, is read again turned a quarter, three quarters and half round, one turn at a time, and the first turn that reads as upright text replaces it; all 20 camera captures were sideways. Docling reads a garbled page, in its place, through [ADR 0059](0059-a-born-digital-pdf-is-read-from-its-text-layer.md)'s splice; a scan with no page that stands goes to Docling whole, as before, and an image with a garbled frame too. Tables stay with OCR.
- **Figures.** Ingest keeps none for a scan read this way, and a scan's figures wait until the agent or Studio asks, as a PDF over 40 pages does: the figures-only pass reads scanned pages with Docling in full, about 39 CPU-s a page, which would give back the CPU this saves. A PDF with born-digital pages beside its scans still gets the pass queued at idle. An image is still its own figure.
- `SURFSENSE_LOCAL_SCAN_OCR=off` reads every scan and photo with Docling, as before; `rapidocr` uses RapidOCR on a Mac too. A value it cannot read also means off. `worker --check-scan-ocr` reads a rendered line with each reader in the frozen worker on every release build.
- **Rejected: Windows' own OCR** (Windows.Media.Ocr, through pywinrt). It read a page in 0.13 to 0.24 s, and worked frozen, but found 0.61 of a form's words and 0.43 of a receipt photo's, writes a table column by column, and nothing in its output told its good pages from its bad ones: keeping only its cleanest-looking pages still lost 7 to 10 points of words against RapidOCR.
- **Rejected: Docling for table pages.** Its Markdown answered table questions worse than RapidOCR's rows, and paid its cold start and 39 CPU-s a page.
- **Rejected: page-parallel tuning beyond 4 pages.** RapidOCR costs about 8 CPU-s a page however it is split; 8 pages at once took 184 s for 100 pages against 209 s for 4 and 192 s for one page on 8 threads, at more CPU.

## Consequences

- A scan's pages no longer import Docling unless one is garbled, so a worker that sees only scans skips Docling's cold start and its 1 GB, until a figures-only pass runs.
- Through the upload route and a real `worker.py ingest`, the six public scanned PDFs and the three book scans, 199 pages in one upload, were all ready in 509 s against 829 s through Docling, a file in 332 s on average against 598 s, for 1,752 worker CPU-s against 7,343. No page went to Docling. A 25-page court filing was ready 47 s after upload, against 614 s as Docling's long readings gave way to each other; its job took 46 s against 130 s. 40 receipt photos, receipt scans and forms in one upload were all ready in 113 s against 202 s, an image in 65 s on average against 129 s, for 131 worker CPU-s against 1,416; none went to Docling. RapidOCR reads about 2 s a page on this machine, so a scan is ready in seconds a page, not in seconds: Windows' own OCR was ten times as fast and read too little.
- Docling's headings and pipe tables are gone from a scan's text; ADR 0059 found the same trade for text-layer PDFs to the app's benefit.
- An image's text is RapidOCR's or Vision's whole, or Docling's whole: Docling cannot be given one frame of a multi-frame TIFF.

## Where the code stands

- Speed is measured on one machine. On it, RapidOCR under Linux (WSL's Ubuntu 24.04) read the same 100 pages in 174 s and 684 CPU-s, against 209 s and 824 under Windows, with the same text; CI runs its tests on Ubuntu, macOS and Windows. Vision's speed is from a virtual Mac with no Neural Engine, so a real Mac should read faster; its accuracy is from that runner.
- A long OCR-first reading checks for a cancel every 8 pages but does not give way to other uploads, as a long Docling reading does: a 100-page scan holds the queue for about 3 minutes. When its garbled pages go to a Docling reading that gives way, OCR's pages are kept, so the resumed run does not read them again.
- Camera captures shot at an angle are read upright, but RapidOCR's rows can still mix lines a perspective skews; Vision read them well.
- PP-OCRv6 covers Latin, Chinese and Japanese, as Docling's did, so scanned Korean, Cyrillic, Devanagari or Arabic text is misread, and Vision's languages are the system's.
