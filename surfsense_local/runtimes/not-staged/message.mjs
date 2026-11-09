// Why a native runtime was not staged on this machine. It is setup to fix,
// not a fault in the script, so it is printed alone, without a stack trace.

import { installCommands } from "./install-commands.mjs"

/** Thrown under --strict; a stage script prints its message and exits 1. */
export class NotStaged extends Error {}

/** Every missing tool and the command that installs them all; null if none is. */
export function notStaged(runtime, how, missing, manager) {
  if (missing.length === 0) return null
  const names = missing.map((tool) => tool.name)
  const lacks =
    names.length > 1 ? `${names.slice(0, -1).join(", ")} and ${names.at(-1)}` : names[0]
  const found = `${runtime} is not staged: ${how}, and this machine lacks ${lacks}.`
  const commands = installCommands(missing, manager)
  return commands.length
    ? `${found} Install what is missing, then run the build again:\n\n${commands.map((command) => `  ${command}`).join("\n")}`
    : `${found} Install what is missing and run the build again.`
}
