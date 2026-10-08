import { createContext, useContext } from "react"

/** The formats LibreOffice lays out exactly and recalculates. */
export const OFFICE_FORMATS: ReadonlySet<string> = new Set([
  "docx",
  "xlsx",
  "pptx",
])

/** What an agent thread needs to offer Office support under a reply: which
 *  artifacts are Office files, and where its consent is. Null where no
 *  workspace is mounted. */
export type OfficeOffer = {
  isOfficeFile: (artifactId: number) => boolean
  openOfficeSupport: () => void
}

export const OfficeOfferContext = createContext<OfficeOffer | null>(null)

export function useOfficeOffer() {
  return useContext(OfficeOfferContext)
}
