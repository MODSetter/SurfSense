// Signs many files through Azure Trusted Signing in one Invoke-TrustedSigning
// run, which the module splits into a few signtool calls. electron-builder's
// own Azure path starts PowerShell once per file, 3.1 to 4.4 s each on 2.2.5's
// tag build: about 20 minutes more for the 300 or so libraries.
import { execFileSync } from "node:child_process"
import { rmSync, writeFileSync } from "node:fs"
import { isAbsolute, join, relative } from "node:path"

import { powershell, quoted } from "./powershell.mjs"

// Seconds per signtool call, the module's default 300 raised: a call takes
// 10,000 characters of paths, about 80 files here, torch's largest among them.
const BATCH_TIMEOUT_S = 1200

/** Signs `files`, all of them under `besideDir`, where the list is written for the module. */
export function signWithAzure(files, azureSignOptions, besideDir) {
  const catalog = join(besideDir, "native-libraries-to-sign.txt")
  writeFileSync(catalog, catalogLines(besideDir, files), "utf8")
  try {
    execFileSync(powershell(), ["-NoProfile", "-NonInteractive", "-Command", azureSigningScript(catalog, azureSignOptions)], {
      stdio: "inherit",
    })
  } finally {
    rmSync(catalog, { force: true })
  }
}

/** The module joins each line to the catalog's folder, and a blank line would join to the folder itself. */
export function catalogLines(dir, files) {
  return files
    .map((file) => {
      const path = relative(dir, file)
      if (path.startsWith("..") || isAbsolute(path)) throw new Error(`${file} is outside ${dir}`)
      return path
    })
    .join("\n")
}

/** The account, digests and timestamp electron-builder's own Azure signing passes. */
export function azureSigningScript(
  catalog,
  { publisherName: _publisher, endpoint, certificateProfileName, codeSigningAccountName, fileDigest, timestampRfc3161, timestampDigest, ...extra }
) {
  const params = {
    ...extra,
    Endpoint: endpoint,
    CertificateProfileName: certificateProfileName,
    CodeSigningAccountName: codeSigningAccountName,
    TimestampRfc3161: timestampRfc3161 || "http://timestamp.acs.microsoft.com",
    TimestampDigest: timestampDigest || "SHA256",
    FileDigest: fileDigest || "SHA256",
    Timeout: BATCH_TIMEOUT_S,
    FilesCatalog: catalog,
  }
  const args = Object.entries(params)
    .filter(([, value]) => value != null)
    .map(([name, value]) => `-${name} ${quoted(value)}`)
    .join(" ")
  return [
    "$ErrorActionPreference = 'Stop'",
    // electron-builder installs it before signing the first .exe; this covers a
    // build that signed none, or a PowerShell other than the one it used.
    "if (-not (Get-Module -ListAvailable -Name TrustedSigning)) { Install-Module -Name TrustedSigning -MinimumVersion 0.5.0 -Force -Repository PSGallery -Scope CurrentUser }",
    `Invoke-TrustedSigning ${args}`,
  ].join("; ")
}
