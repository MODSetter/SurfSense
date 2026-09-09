import type { Citation } from "./sse"

const CODE_REGION = /(```[\s\S]*?```|`[^`\n]+`)/g
const CITATION_TOKEN = /\[citation:\s*(\d+)\s*\]/g
const ORDINAL = /\[(\d+)\]/g

function chunkIdFor(token: number, citations: Citation[]) {
  if (citations.some((citation) => citation.chunk_id === token)) {
    return token
  }
  return (
    citations.find((citation) => citation.source_id === token)?.chunk_id ??
    token
  )
}

export function preprocessCitationMarkdown(
  content: string,
  citations: Citation[] = []
) {
  return content
    .split(CODE_REGION)
    .map((part, index) => {
      if (index % 2 === 1) {
        return part
      }
      const marked = part.replace(CITATION_TOKEN, (_match, raw: string) => {
        const chunkId = chunkIdFor(Number(raw), citations)
        return `<citation data-chunk-id="${chunkId}">${chunkId}</citation>`
      })
      if (citations.length === 0) {
        return marked
      }
      return marked.replace(ORDINAL, (match, raw: string) => {
        const source = citations.find(
          (citation) => citation.source_id === Number(raw)
        )
        if (!source) {
          return match
        }
        return `<citation data-chunk-id="${source.chunk_id}">${source.chunk_id}</citation>`
      })
    })
    .join("")
}
