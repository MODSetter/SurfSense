import { homedir } from "node:os"
import { stripVTControlCharacters } from "node:util"

/** This run's output, oldest line first. Held in memory, so it ends with the app. */
export type SessionLog = {
  append(source: string, text: string): void
  lines(): string[]
}

// Hours of use once polling is dropped, and small enough to send whole on every read.
const MAX_LINES = 2000
// A minified bundle or a base64 blob on one line would otherwise crowd out the rest.
const MAX_LINE_LENGTH = 2000

// ponytail: uvicorn's default access-log format. Electron and the renderer poll
// the API, so its successful reads would fill the log; a changed format lets
// them through rather than hiding anything else.
const SUCCESSFUL_READ = /^INFO: +\S+ - "GET [^"]*" [23]\d\d\b/

export function createSessionLog(options: {
  home: string
  now?: () => Date
  maxLines?: number
}): SessionLog {
  const { home, now = () => new Date(), maxLines = MAX_LINES } = options
  // The log is pasted into public issues. A Windows home shows up as written,
  // with forward slashes, and escaped in a Python repr.
  const homes = [
    ...new Set([home, home.replaceAll("\\", "/"), home.replaceAll("\\", "\\\\")]),
  ]
    .filter((path) => path.length > 0)
    .sort((a, b) => b.length - a.length)
  const kept: string[] = []

  return {
    append(source, text) {
      const time = now().toTimeString().slice(0, 8)
      for (const raw of stripVTControlCharacters(text).split(/\r?\n/)) {
        let line = raw.trimEnd()
        if (!line || SUCCESSFUL_READ.test(line)) continue
        for (const path of homes) line = line.replaceAll(path, "~")
        if (line.length > MAX_LINE_LENGTH) line = `${line.slice(0, MAX_LINE_LENGTH)}…`
        kept.push(`${time} [${source}] ${line}`)
        if (kept.length > maxLines) kept.shift()
      }
    },
    lines: () => [...kept],
  }
}

export const sessionLog = createSessionLog({ home: homedir() })
