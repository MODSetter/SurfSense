import ts from "typescript"
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

function isTypeOnly(node: ts.ImportDeclaration | ts.ExportDeclaration) {
  if (ts.isExportDeclaration(node)) return node.isTypeOnly
  const clause = node.importClause
  if (!clause) return false
  if (clause.isTypeOnly) return true
  // `import { type A, type B }`, with nothing else, loads nothing either.
  const bindings = clause.namedBindings
  return (
    !clause.name &&
    bindings !== undefined &&
    ts.isNamedImports(bindings) &&
    bindings.elements.length > 0 &&
    bindings.elements.every((element) => element.isTypeOnly)
  )
}

/** The modules a file loads when it loads: static, value imports only. */
function loadedBy(file: string): string[] {
  const source = ts.createSourceFile(
    file,
    SOURCES[file] ?? "",
    ts.ScriptTarget.Latest,
    false,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  )
  const specifiers: string[] = []
  for (const statement of source.statements) {
    if (
      (ts.isImportDeclaration(statement) ||
        ts.isExportDeclaration(statement)) &&
      statement.moduleSpecifier &&
      ts.isStringLiteral(statement.moduleSpecifier) &&
      !isTypeOnly(statement)
    ) {
      specifiers.push(statement.moduleSpecifier.text)
    }
  }
  return specifiers
}

function reachable(entry: string): string[] {
  const seen = new Set<string>()
  const queue = [entry]
  const reached: string[] = []
  while (queue.length > 0) {
    const file = queue.pop()!
    if (seen.has(file)) continue
    seen.add(file)
    for (const specifier of loadedBy(file)) {
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

  it("skip what only names types, which loads nothing", () => {
    // It names assistant-ui's matcher type only.
    expect(
      loadedBy("/src/features/plugins/in-thread/mention-matcher.ts")
    ).toEqual([])
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
