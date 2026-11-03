import { describe, expect, it } from "vitest"

// The startup screen ships in the first chunk, before the dashboard's. If it
// reached the chat runtime or a feature's API client, that code would load
// before anything is drawn and the frame would arrive late.
const FORBIDDEN = [
  /^@assistant-ui\//,
  /^@tanstack\/react-query/,
  /^\/src\/features\/.+\/api\.ts$/,
]

// Every source file's text, keyed from the project root: "/src/…".
const SOURCES = import.meta.glob<string>(
  ["/src/**/*.{ts,tsx}", "!/src/**/*.test.{ts,tsx}"],
  { query: "?raw", import: "default", eager: true }
)

function resolveLocal(from: string, specifier: string): string | null {
  const base = specifier.startsWith("@/")
    ? `/src/${specifier.slice(2)}`
    : new URL(specifier, `file://${from}`).pathname
  for (const candidate of [
    base,
    `${base}.ts`,
    `${base}.tsx`,
    `${base}/index.ts`,
    `${base}/index.tsx`,
  ]) {
    if (candidate in SOURCES) return candidate
  }
  return null
}

// Every module the file loads at run time; type-only imports are erased.
function reachable(entry: string): string[] {
  const seen = new Set<string>()
  const queue = [entry]
  const reached: string[] = []
  while (queue.length > 0) {
    const file = queue.pop()!
    if (seen.has(file)) continue
    seen.add(file)
    const imports = (SOURCES[file] ?? "").matchAll(
      /^\s*import\s+(?!type\b)(?:[^"';]*?\sfrom\s+)?["']([^"']+)["']/gm
    )
    for (const [, specifier] of imports) {
      if (specifier.startsWith(".") || specifier.startsWith("@/")) {
        const local = resolveLocal(file, specifier)
        if (local) {
          reached.push(local)
          queue.push(local)
        }
      } else {
        reached.push(specifier)
      }
    }
  }
  return reached
}

describe("startup screen's imports", () => {
  it("are walked deep enough to find the runtime where it is used", () => {
    const reached = reachable("/src/features/chat/thread-panel.tsx")
    expect(reached.some((module) => FORBIDDEN[0]!.test(module))).toBe(true)
    expect(reached.some((module) => FORBIDDEN[2]!.test(module))).toBe(true)
  })

  it("reach neither the chat runtime nor any feature's API client", () => {
    const reached = reachable("/src/features/startup/startup-screen.tsx")
    expect(reached.length).toBeGreaterThan(10)
    expect(
      reached.filter((module) =>
        FORBIDDEN.some((pattern) => pattern.test(module))
      )
    ).toEqual([])
  })
})
