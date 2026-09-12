/**
 * The bundled Ollama server. Packaged only: dev uses the developer's own
 * `ollama serve`, so this returns null and nothing is spawned. Its runners live
 * beside the binary (lib/ollama), which Ollama discovers on its own.
 */
import { existsSync } from "node:fs"
import { join } from "node:path"

import { exe } from "./platform.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"

// The archive layout differs per OS (bin/ollama vs a root-level ollama.exe), so
// resolve the binary rather than assume one shape.
function resolveBinary(dir: string): string {
  const name = exe("ollama")
  const candidates = [join(dir, "bin", name), join(dir, name)]
  return candidates.find(existsSync) ?? candidates[0]
}

export function ollamaSpec(ctx: SidecarContext): SidecarSpec | null {
  if (!ctx.packaged || ctx.ollamaPort == null || !ctx.ollamaModelsDir) return null

  const dir = join(ctx.binariesDir, "ollama")
  return {
    name: "ollama",
    cmd: resolveBinary(dir),
    args: ["serve"],
    cwd: dir,
    env: {
      OLLAMA_HOST: `${ctx.host}:${ctx.ollamaPort}`,
      OLLAMA_MODELS: ctx.ollamaModelsDir,
    },
  }
}
