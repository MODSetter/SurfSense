import { bugReportUrl } from "@/features/about/about-links"

/** A bug form GitHub prefills from the link, and the part the user pastes in. */
export type PrefilledIssue = {
  url: string
  // Field ids in .github/ISSUE_TEMPLATE/bug.yml.
  paste: { text: string; into: "logs" | "what" } | null
}

// Electron's shell.openExternal refuses longer links on Windows.
const MAX_URL_LENGTH = 2081
// GitHub refuses an issue body over 65,536 characters, and the form's other fields share it.
const MAX_LOG_LENGTH = 50_000
const MAX_TITLE_LENGTH = 50

export function prefilledIssue(report: {
  description: string
  error?: string
  system?: string
  log: string[]
}): PrefilledIssue {
  const description = report.description.trim()
  const firstLine = [...description.split("\n", 1)[0].trim()]
  const title = `[bug] ${
    firstLine.length > MAX_TITLE_LENGTH
      ? `${firstLine.slice(0, MAX_TITLE_LENGTH - 1).join("")}…`
      : firstLine.join("")
  }`
  const what = [
    description,
    report.error && `Error: ${report.error}`,
    report.system && `---\n${report.system}`,
  ]
    .filter(Boolean)
    .join("\n\n")
  const log = logTail(report.log)

  const url = bugReportUrl(what, title)
  if (url.length <= MAX_URL_LENGTH) {
    return { url, paste: log ? { text: log, into: "logs" } : null }
  }
  // A long description, or one in a script that takes 9 characters a letter to encode.
  return {
    url: bugReportUrl("", title),
    paste: {
      text: log ? `${what}\n\n\`\`\`text\n${log}\n\`\`\`` : what,
      into: "what",
    },
  }
}

// The newest lines are the ones that explain what just went wrong.
function logTail(lines: string[]): string {
  let size = 0
  let start = lines.length
  while (start > 0 && size + lines[start - 1].length + 1 <= MAX_LOG_LENGTH) {
    start -= 1
    size += lines[start].length + 1
  }
  const kept = lines.slice(start)
  return (
    start > 0 ? [`… ${start} earlier lines left out`, ...kept] : kept
  ).join("\n")
}
