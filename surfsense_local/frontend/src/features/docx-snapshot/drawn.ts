/** Settles once the image has loaded or failed; a broken image still prints. */
export function drawn(image: HTMLImageElement): Promise<void> {
  if (image.complete) return Promise.resolve()
  return new Promise((resolve) => {
    image.addEventListener("load", () => resolve(), { once: true })
    image.addEventListener("error", () => resolve(), { once: true })
  })
}
