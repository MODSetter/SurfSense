import { execFile } from "node:child_process"
import { normalize } from "node:path"

// electron-updater 6.8.9's Windows check (windowsExecutableCodeSignatureVerifier.js)
// minus its publisher match: the signed manifest pins the installer's sha512
// (ADR 0091), and 2.4.0 cannot know the names later certificates carry. The
// PowerShell call, its 20 s bound and its skip are electron-updater's own.

export type UpdaterLog = { info(message: string): void; warn(message: string): void }
/** NsisUpdater.verifyUpdateCodeSignature: null passes; a reason refuses the installer. */
export type VerifyUpdateCodeSignature = (publisherNames: string[], file: string) => Promise<string | null>
/** One PowerShell command's stdout; rejects when it fails or writes to stderr. */
export type RunPowerShell = (command: string, timeoutMs: number) => Promise<string>

// System.Management.Automation.SignatureStatus, in order.
const STATUS = ["Valid", "UnknownError", "NotSigned", "HashMismatch", "NotTrusted", "NotSupportedFileFormat", "Incompatible"]

export function acceptAnyTrustedPublisher(
  log: UpdaterLog,
  run: RunPowerShell = runPowerShell
): VerifyUpdateCodeSignature {
  return async (_publisherNames, file) => {
    log.info(`Verifying signature ${file}`)
    let reading: string
    try {
      // Single quotes doubled, as electron-updater does, so a path cannot end the string.
      reading = await run(`Get-AuthenticodeSignature -LiteralPath '${file.replace(/'/g, "''")}' | ConvertTo-Json -Compress`, 20_000)
    } catch (error) {
      if (await cannotRunConvertToJson(run)) {
        log.warn(`Cannot execute Get-AuthenticodeSignature: ${String(error)}. Ignoring signature validation due to unsupported powershell version.`)
        return null
      }
      throw error
    }
    return verdict(JSON.parse(reading), file, log)
  }
}

function verdict(
  data: { Status?: unknown; Path?: unknown; SignerCertificate?: { Subject?: unknown } | null },
  file: string,
  log: UpdaterLog
): string | null {
  if (data.Status !== 0) {
    const status = typeof data.Status === "number" ? (STATUS[data.Status] ?? String(data.Status)) : "unknown"
    log.warn(`Windows does not trust the installer's signature: ${status}`)
    return `Windows does not trust its signature (${status})`
  }
  // Proof the answer is about this file; an answer with no path skips the check, as electron-updater's does.
  if (typeof data.Path === "string" && normalize(data.Path) !== normalize(file)) {
    throw new Error(`LiteralPath of ${normalize(data.Path)} is different than ${normalize(file)}`)
  }
  log.info(`Installer signed by ${String(data.SignerCertificate?.Subject ?? "an unnamed publisher")}, which Windows trusts`)
  return null
}

async function cannotRunConvertToJson(run: RunPowerShell): Promise<boolean> {
  try {
    await run("ConvertTo-Json test", 10_000)
    return false
  } catch {
    return true
  }
}

function runPowerShell(command: string, timeoutMs: number): Promise<string> {
  return new Promise((resolve, reject) => {
    // electron-updater's invocation: PSModulePath cleared (electron-builder#7127)
    // and UTF-8 output, so a publisher name with an umlaut still parses.
    execFile(
      `set "PSModulePath=" & chcp 65001 >NUL & powershell.exe`,
      ["-NoProfile", "-NonInteractive", "-InputFormat", "None", "-Command", `"${command}"`],
      { shell: true, timeout: timeoutMs },
      (error, stdout, stderr) => {
        if (error) reject(error)
        else if (stderr) reject(new Error(`Cannot execute Get-AuthenticodeSignature, stderr: ${stderr}`))
        else resolve(stdout)
      }
    )
  })
}
