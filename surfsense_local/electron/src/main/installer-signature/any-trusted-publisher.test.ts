import assert from "node:assert/strict"
import { closeSync, copyFileSync, mkdtempSync, openSync, rmSync, statSync, writeFileSync, writeSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { acceptAnyTrustedPublisher, type RunPowerShell } from "./any-trusted-publisher.ts"

const INSTALLER = "C:\\Users\\me\\AppData\\Local\\surfsense-local-electron-updater\\pending\\temp-SurfSense-Setup.exe"

function recorder() {
  const lines: string[] = []
  return { lines, log: { info: (line: string) => lines.push(line), warn: (line: string) => lines.push(line) } }
}

/** Get-AuthenticodeSignature's answer, as ConvertTo-Json writes it, for every command. */
function answering(reading: object): { run: RunPowerShell; commands: string[] } {
  const commands: string[] = []
  return {
    commands,
    run: async (command) => {
      commands.push(command)
      return JSON.stringify(reading)
    },
  }
}

test("an installer Windows trusts passes, whoever signed it", async () => {
  // 2.4.0's app-update.yml names SurfSense; a later certificate may name anyone.
  const { run } = answering({
    Status: 0,
    Path: INSTALLER,
    SignerCertificate: { Subject: "CN=Jane Doe, O=Jane Doe, L=Austin, S=Texas, C=US" },
  })
  const { lines, log } = recorder()

  assert.equal(await acceptAnyTrustedPublisher(log, run)(["SurfSense"], INSTALLER), null)
  assert.ok(lines.some((line) => line.includes("CN=Jane Doe")))
})

for (const [status, name] of [
  [2, "NotSigned"],
  [3, "HashMismatch"],
  [4, "NotTrusted"],
  [1, "UnknownError"],
] as const) {
  test(`an installer whose signature is ${name} is refused`, async () => {
    const { run } = answering({ Status: status, Path: INSTALLER, SignerCertificate: null })

    assert.equal(
      await acceptAnyTrustedPublisher(recorder().log, run)(["SurfSense"], INSTALLER),
      `Windows does not trust its signature (${name})`
    )
  })
}

test("an answer about another file fails the check", async () => {
  const { run } = answering({ Status: 0, Path: "C:\\Windows\\notepad.exe", SignerCertificate: { Subject: "CN=x" } })

  await assert.rejects(acceptAnyTrustedPublisher(recorder().log, run)(["SurfSense"], INSTALLER), /LiteralPath/)
})

test("a path holding a single quote cannot end PowerShell's string", async () => {
  const file = "C:\\Users\\o'brien\\temp-SurfSense-Setup.exe"
  const { run, commands } = answering({ Status: 0, Path: file, SignerCertificate: { Subject: "CN=x" } })

  await acceptAnyTrustedPublisher(recorder().log, run)(["SurfSense"], file)

  assert.deepEqual(commands, [
    "Get-AuthenticodeSignature -LiteralPath 'C:\\Users\\o''brien\\temp-SurfSense-Setup.exe' | ConvertTo-Json -Compress",
  ])
})

test("a PowerShell that cannot run ConvertTo-Json skips the check, as electron-updater does", async () => {
  const run: RunPowerShell = async () => {
    throw new Error("'powershell.exe' is not recognized")
  }
  const { lines, log } = recorder()

  assert.equal(await acceptAnyTrustedPublisher(log, run)(["SurfSense"], INSTALLER), null)
  assert.ok(lines.some((line) => line.includes("Ignoring signature validation")))
})

test("a check PowerShell fails while it still runs ConvertTo-Json stops the update", async () => {
  const run: RunPowerShell = async (command) => {
    if (command === "ConvertTo-Json test") return '"test"'
    throw new Error("Cannot execute Get-AuthenticodeSignature, stderr: denied")
  }

  await assert.rejects(acceptAnyTrustedPublisher(recorder().log, run)(["SurfSense"], INSTALLER), /denied/)
})

const onWindows = { skip: process.platform !== "win32" && "Get-AuthenticodeSignature is Windows-only" }

test("on Windows, a binary another trusted publisher signed passes: Node's own node.exe", onWindows, async (t) => {
  const { lines, log } = recorder()
  const verify = acceptAnyTrustedPublisher(log)
  const answer = await verify(["SurfSense"], process.execPath)
  // A Node built from source carries no signature to test with.
  if (answer?.includes("NotSigned")) return t.skip("this node.exe is not Authenticode-signed")
  assert.equal(answer, null)
  assert.ok(lines.some((line) => line.includes("OpenJS Foundation")), lines.join("\n"))
})

test("on Windows, a signed binary changed after signing, and a file never signed, are refused", onWindows, async (t) => {
  const dir = mkdtempSync(join(tmpdir(), "installer-signature-"))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const verify = acceptAnyTrustedPublisher(recorder().log)
  if ((await verify([], process.execPath)) !== null) return t.skip("this node.exe is not Authenticode-signed")

  const tampered = join(dir, "temp-SurfSense-Setup.exe")
  copyFileSync(process.execPath, tampered)
  const fd = openSync(tampered, "r+")
  writeSync(fd, Buffer.from([0x5a]), 0, 1, Math.floor(statSync(tampered).size / 2))
  closeSync(fd)
  assert.equal(await verify(["SurfSense"], tampered), "Windows does not trust its signature (HashMismatch)")

  const unsigned = join(dir, "unsigned-SurfSense-Setup.exe")
  writeFileSync(unsigned, "not an installer")
  assert.match((await verify(["SurfSense"], unsigned)) ?? "", /^Windows does not trust its signature \(/)
})
