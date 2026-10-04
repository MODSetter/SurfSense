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

import { opencodeFolders } from "./opencode-home.ts"
import { exe } from "./platform.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"

export const OPENCODE_SIDECAR = "opencode"

/** The configuration the API writes; opencode reads it through OPENCODE_CONFIG. */
export const CONFIG_FILE = "opencode.json"

// What the operating system must still provide for the server and its shell.
// Home and proxies are not among them: those are set below.
const FROM_THE_SYSTEM = [
  "PATH",
  "TMPDIR",
  "TEMP",
  "TMP",
  "LANG",
  "LC_ALL",
  "LC_CTYPE",
  "TZ",
  "SYSTEMROOT",
  "WINDIR",
  "COMSPEC",
  "PATHEXT",
]

// Each fetch opencode would make on its own, switched off
// (docs/proposals/agent/03-opencode.md, No network).
const SWITCHED_OFF = [
  "OPENCODE_DISABLE_MODELS_FETCH",
  "OPENCODE_DISABLE_SHARE",
  "OPENCODE_DISABLE_LSP_DOWNLOAD",
  "OPENCODE_DISABLE_AUTOUPDATE",
  "OPENCODE_DISABLE_DEFAULT_PLUGINS",
  "OPENCODE_PURE",
  "OPENCODE_DISABLE_PROJECT_CONFIG",
  "OPENCODE_DISABLE_EXTERNAL_SKILLS",
  "OPENCODE_DISABLE_CLAUDE_CODE",
]

// The discard port: nothing a desktop runs listens there, so a fetch this
// misses fails instead of leaving the machine. Models and tools are on loopback.
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
  const { opencodeBinariesDir, opencodePort, opencodePassword, agentDir } = ctx
  if (
    opencodeBinariesDir == null ||
    opencodePort == null ||
    opencodePassword == null ||
    agentDir == null
  ) {
    return null
  }
  const binary = binaryPath(ctx)
  if (!existsSync(binary) || !existsSync(configPath(agentDir))) return null

  return {
    name: OPENCODE_SIDECAR,
    cmd: binary,
    args: ["serve", "--hostname", ctx.host, "--port", String(opencodePort)],
    cwd: opencodeFolders(agentDir).home,
    env: opencodeEnvironment(opencodeBinariesDir, opencodePassword, agentDir),
    inheritEnv: false,
  }
}

/** Everything opencode's process gets, from the system's few variables up. */
function opencodeEnvironment(
  binariesDir: string,
  password: string,
  agentDir: string
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
    OPENCODE_CONFIG: configPath(agentDir),
    OPENCODE_SERVER_PASSWORD: password,
    ...Object.fromEntries(SWITCHED_OFF.map((flag) => [flag, "1"])),
    // A case the npm stub misses fails at once, rather than waiting on retries.
    npm_config_audit: "false",
    npm_config_fetch_retries: "0",
    HTTP_PROXY: NOWHERE,
    HTTPS_PROXY: NOWHERE,
    ALL_PROXY: NOWHERE,
    http_proxy: NOWHERE,
    https_proxy: NOWHERE,
    all_proxy: NOWHERE,
    NO_PROXY: LOOPBACK,
    no_proxy: LOOPBACK,
  }
}
