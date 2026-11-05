import { readFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import type { Plugin } from "vite"

const SUFFIX = ".wasm?data-url"
// A virtual id: under node_modules, Vitest would hand the real path to Node.
const PREFIX = "virtual:wasm-data-url:"

/** `import url from "./x.wasm?data-url"`: Vite's own ?inline does not reach .wasm. */
export function wasmDataUrl(): Plugin {
  return {
    name: "wasm-data-url",
    enforce: "pre",
    resolveId: (source, importer) =>
      source.endsWith(SUFFIX) && importer
        ? `${PREFIX}${resolve(dirname(importer.split("?")[0]), source.slice(0, -"?data-url".length))}`
        : null,
    async load(id) {
      if (!id.startsWith(PREFIX)) return null
      const bytes = await readFile(id.slice(PREFIX.length))
      return `export default "data:application/wasm;base64,${bytes.toString("base64")}"`
    },
  }
}
