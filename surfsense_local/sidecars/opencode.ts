/**
 * opencode's server: the agent's engine. Like sd-server it does not start at
 * boot. The API writes its configuration the first time a thread needs the
 * agent, and index.ts starts it then and restarts it on every rewrite.
 *
 * Its environment is built here from nothing. Shell commands the agent runs
 * inherit opencode's whole environment, and Electron's holds the secret that
 * decrypts every stored API key.
 */
import { existsSync } from "node:fs"
import { delimiter, join } from "node:path"

import { oneSpelling } from "./opencode-folder-spelling.ts"
import { opencodeFolders } from "./opencode-home.ts"
import { exe } from "./platform.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"

export const OPENCODE_SIDECAR = "opencode"

/** The configuration the API writes; opencode reads it through OPENCODE_CONFIG. */
export const CONFIG_FILE = "opencode.json"

// What the operating system must still provide for the server and its shell.
// Home, temp and proxies are not among them: those are set below.
const FROM_THE_SYSTEM = [
  "PATH",
  "LANG",
  "LC_ALL",
  "LC_CTYPE",
  "TZ",
  "SYSTEMROOT",
  "WINDIR",
  "COMSPEC",
  "PATHEXT",
]

// What 2.x still switches off from its environment; the rest of what it would
// fetch or load on its own is switched off in the configuration
// (docs/architecture/packaging.md).
const SWITCHED_OFF = [
  "OPENCODE_DISABLE_MODELS_FETCH",
  "OPENCODE_DISABLE_CLAUDE_CODE",
  "OPENCODE_CONFIG_PROJECT_DISABLE",
]

// The discard port: nothing a desktop runs listens there, so a fetch fails
// instead of leaving the machine. Models and tools are on loopback; plugins go
// through the API's proxy, which tunnels only a ready plugin's host.
const NOWHERE = "http://127.0.0.1:9"
const LOOPBACK = "127.0.0.1,localhost,::1"

export function binaryPath(ctx: SidecarContext): string {
  return join(ctx.opencodeBinariesDir ?? "", exe("opencode"))
}

export function configPath(agentDir: string): string {
  return join(agentDir, CONFIG_FILE)
}

/** Null until it can run: a build staged, and the API's configuration on disk. */
export function opencodeSpec(ctx: SidecarContext): SidecarSpec | null {
  const { opencodeBinariesDir, opencodePort, opencodePassword } = ctx
  if (
    opencodeBinariesDir == null ||
    opencodePort == null ||
    opencodePassword == null ||
    ctx.agentDir == null
  ) {
    return null
  }
  const agentDir = oneSpelling(ctx.agentDir)
  const binary = binaryPath(ctx)
  if (!existsSync(binary) || !existsSync(configPath(agentDir))) return null

  return {
    name: OPENCODE_SIDECAR,
    cmd: binary,
    args: ["serve", "--hostname", ctx.host, "--port", String(opencodePort)],
    cwd: opencodeFolders(agentDir).home,
    env: opencodeEnvironment(
      opencodeBinariesDir,
      opencodePassword,
      agentDir,
      ctx.opencodeProxyPort == null ? NOWHERE : `http://${ctx.host}:${ctx.opencodeProxyPort}`
    ),
    inheritEnv: false,
  }
}

/** Everything opencode's process gets, from the system's few variables up. */
function opencodeEnvironment(
  binariesDir: string,
  password: string,
  agentDir: string,
  proxy: string
): Record<string, string> {
  const system: Record<string, string> = {}
  for (const name of FROM_THE_SYSTEM) {
    const value = process.env[name]
    if (value !== undefined) system[name] = value
  }
  const folders = opencodeFolders(agentDir)
  return {
    ...system,
    // The shipped `rg` first, or opencode downloads ripgrep from GitHub.
    PATH: [binariesDir, system.PATH].filter(Boolean).join(delimiter),
    HOME: folders.home,
    USERPROFILE: folders.home,
    // opencode reads its home from here before os.homedir().
    OPENCODE_TEST_HOME: folders.home,
    XDG_CONFIG_HOME: folders.config,
    XDG_DATA_HOME: folders.data,
    XDG_CACHE_HOME: folders.cache,
    XDG_STATE_HOME: folders.state,
    // Its scratch folder is $TMPDIR/opencode, shared with the user's own opencode.
    TMPDIR: folders.temp,
    TEMP: folders.temp,
    TMP: folders.temp,
    OPENCODE_CONFIG: configPath(agentDir),
    OPENCODE_PASSWORD: password,
    ...Object.fromEntries(SWITCHED_OFF.map((flag) => [flag, "1"])),
    HTTP_PROXY: proxy,
    HTTPS_PROXY: proxy,
    ALL_PROXY: proxy,
    http_proxy: proxy,
    https_proxy: proxy,
    all_proxy: proxy,
    NO_PROXY: LOOPBACK,
    no_proxy: LOOPBACK,
  }
}
