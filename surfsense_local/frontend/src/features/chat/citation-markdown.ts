const CODE_REGION = /(```[\s\S]*?```|`[^`\n]+`)/g
const CITATION_TOKEN = /\[citation:\s*(\d+)\s*\]/g

export function preprocessCitationMarkdown(content: string) {
  return content
    .split(CODE_REGION)
    .map((part, index) =>
      index % 2 === 1
        ? part
        : part.replace(
            CITATION_TOKEN,
            '<citation data-source-id="$1">$1</citation>'
          )
    )
    .join("")
}
