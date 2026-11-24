import { execFile } from "node:child_process"
import { createReadStream } from "node:fs"
import { normalize } from "node:path"
import { Writable } from "node:stream"
import { pipeline } from "node:stream/promises"

// electron-updater 6.8.9's Windows check (windowsExecutableCodeSignatureVerifier.js)
// minus its publisher match: the signed manifest pins the installer's sha512
// (ADR 0091), and 2.4.0 cannot know the names later certificates carry. The
// PowerShell call and its skip are electron-updater's own; its 20 s bound is not.
//
// Microsoft Defender scans a new executable when something first opens it, and
// the check waits for that scan. On the 1 GB installer the scan alone took 6-7 s,
// and longer on a first try: two of a maintainer's three updates from 2.3.1 to
// 2.4.0 stopped at electron-updater's 20 s, which 2.3.x and 2.4.0 still apply.
// So the installer is read once first, outside any bound, which leaves the scan
// done and the file cached for the hash, and the check itself gets two minutes.
const CHECK_TIMEOUT_MS = 120_000

export type UpdaterLog = { info(message: string): void; warn(message: string): void }
/** NsisUpdater.verifyUpdateCodeSignature: null passes; a reason refuses the installer. */
export type VerifyUpdateCodeSignature = (publisherNames: string[], file: string) => Promise<string | null>
/** One PowerShell command's stdout; rejects when it fails or writes to stderr. */
export type RunPowerShell = (command: string, timeoutMs: number) => Promise<string>
/** Reads a file to its end, keeping nothing. */
export type ReadThrough = (file: string) => Promise<void>

// System.Management.Automation.SignatureStatus, in order.
const STATUS = ["Valid", "UnknownError", "NotSigned", "HashMismatch", "NotTrusted", "NotSupportedFileFormat", "Incompatible"]

export function acceptAnyTrustedPublisher(
  log: UpdaterLog,
  run: RunPowerShell = runPowerShell,
  readThrough: ReadThrough = readToEnd
): VerifyUpdateCodeSignature {
  return async (_publisherNames, file) => {
    log.info(`Verifying signature ${file}`)
    try {
      await readThrough(file)
    } catch (error) {
      // PowerShell reads it next and reports anything that is really wrong.
      log.warn(`Could not read the installer before checking its signature: ${String(error)}`)
    }
    let reading: string
    try {
      // Single quotes doubled, as electron-updater does, so a path cannot end the string.
      reading = await run(`Get-AuthenticodeSignature -LiteralPath '${file.replace(/'/g, "''")}' | ConvertTo-Json -Compress`, CHECK_TIMEOUT_MS)
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

function readToEnd(file: string): Promise<void> {
  return pipeline(
    createReadStream(file, { highWaterMark: 1024 * 1024 }),
    new Writable({ write: (_chunk, _encoding, done) => done() })
  )
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
