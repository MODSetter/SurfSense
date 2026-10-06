import {
  buildPresentation,
  parseZip,
  RECOMMENDED_ZIP_LIMITS,
  renderSlide,
  type SlideRendererOptions,
} from "@aiden0z/pptx-renderer"

import { drawn } from "./drawn"
import { slidePrintLayout } from "./slide-print-layout"

// ECharts animates a chart in over about a second; a chart that never says it
// has finished is printed as it stands after this.
const CHART_MS = 3000

type Chart =
  NonNullable<SlideRendererOptions["chartInstances"]> extends Set<infer C>
    ? C
    : never

/** Lay a PowerPoint deck out in `page` with the in-app viewer's library, one
 *  slide per printed page, and settle once its slides are drawn. */
export async function layOutDeck(file: ArrayBuffer, page: Document) {
  const deck = buildPresentation(await parseZip(file, RECOMMENDED_ZIP_LIMITS))
  const charts = new Set<Chart>()
  // One cache for every slide, so a picture the slides share is one object
  // URL; the window is thrown away after printing, which frees them.
  const mediaUrlCache = new Map<string, string>()

  const style = page.createElement("style")
  style.textContent = slidePrintLayout(deck.width, deck.height)
  page.head.append(style)

  const slides = deck.slides.map((slide) => {
    // No pdfjs: an EMF picture's PDF fallback would start a worker.
    const handle = renderSlide(deck, slide, {
      mediaUrlCache,
      chartInstances: charts,
      pdfjs: false,
    })
    const sheet = page.createElement("div")
    sheet.append(handle.element)
    // Charts are drawn only once their slide is in the document.
    page.body.append(sheet)
    return handle
  })

  await Promise.all(slides.map((slide) => slide.ready))
  await Promise.all([...charts].map(chartFinished))
  await Promise.all(backgroundImages(page.body).map(drawn))
}

function chartFinished(chart: Chart): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, CHART_MS)
    chart.on("finished", () => {
      clearTimeout(timer)
      resolve()
    })
  })
}

/** The deck's backgrounds and image fills, which are CSS, not <img>: loaded
 *  into images of their own, since nothing tells when a CSS one has. */
function backgroundImages(root: HTMLElement): HTMLImageElement[] {
  const urls = new Set<string>()
  for (const element of root.querySelectorAll<HTMLElement>("[style]")) {
    for (const [, url] of element.style.backgroundImage.matchAll(
      /url\("?([^")]+)"?\)/g
    )) {
      urls.add(url)
    }
  }
  return [...urls].map((url) => {
    const image = new Image()
    image.src = url
    return image
  })
}
