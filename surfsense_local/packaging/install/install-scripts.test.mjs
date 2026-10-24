import assert from "node:assert/strict"
import { spawn, spawnSync } from "node:child_process"
import { createHash } from "node:crypto"
import { once } from "node:events"
import { copyFileSync, existsSync, linkSync, mkdtempSync, readFileSync, realpathSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

// Run with: node --test surfsense_local/packaging/install/install-scripts.test.mjs
// Every plan comes from a dry run with SURFSENSE_FAKE_* standing in for the
// machine, so nothing here reaches the network or needs root. Only the Windows
// running-app check looks at this machine, at a copy of Node it starts itself.

const posixPath = (url) => fileURLToPath(url).replaceAll("\\", "/")
const INSTALL_SH = posixPath(new URL("./install.sh", import.meta.url))
const INSTALL_PS1 = fileURLToPath(new URL("./install.ps1", import.meta.url))
const BUILDER_YML = new URL("../../electron/electron-builder.yml", import.meta.url)
const THIS_FILE = posixPath(import.meta.url)

const RELEASE = "https://github.com/MODSetter/SurfSense/releases/download/"
const DOWNLOADS_PAGE = "https://www.surfsense.com/downloads"
const APT_LINE =
  "deb [signed-by=/usr/share/keyrings/surfsense-archive-keyring.gpg] https://github.com/MODSetter/SurfSense/releases/latest/download/ ./"

/** This process's environment without any real SURFSENSE_* setting. */
function cleanEnv(vars) {
  const env = Object.fromEntries(
    Object.entries(process.env).filter(([key]) => !key.startsWith("SURFSENSE_"))
  )
  delete env.XDG_DATA_HOME
  return { ...env, ...vars }
}

/** A shell that runs and can read this checkout: on Windows `bash` may be WSL's. */
function workingShell(name) {
  const probe = spawnSync(name, ["-c", 'test -r "$1" && echo ok', "probe", THIS_FILE], {
    encoding: "utf8",
    timeout: 20_000,
  })
  return probe.stdout?.trim() === "ok"
}

const SHELLS = ["sh", "dash", "bash"].filter(workingShell)
const POWERSHELLS = ["powershell", "pwsh"].filter((name) => {
  const probe = spawnSync(name, ["-NoProfile", "-NonInteractive", "-Command", "'ok'"], {
    encoding: "utf8",
    timeout: 60_000,
  })
  return probe.stdout?.trim() === "ok"
})

function shPlan(vars) {
  const result = spawnSync(SHELLS[0], [INSTALL_SH], {
    encoding: "utf8",
    timeout: 60_000,
    env: cleanEnv({
      HOME: "/home/tester",
      TMPDIR: "/var/tmp",
      SURFSENSE_INSTALL_DRY_RUN: "1",
      SURFSENSE_FAKE_LATEST: "v2.2.4",
      // A conventional Linux at the floor, whatever machine runs the tests.
      SURFSENSE_FAKE_GLIBC: "2.35",
      SURFSENSE_FAKE_IMAGE_BASED: "0",
      ...vars,
    }),
  })
  return withSteps(result)
}

function ps1Plan(shell, vars) {
  // The way people run it, `irm ... | iex`, minus the download.
  const result = spawnSync(
    shell,
    [
      "-NoProfile",
      "-NonInteractive",
      "-Command",
      "Get-Content -Raw -LiteralPath $env:SURFSENSE_TEST_SCRIPT | Invoke-Expression",
    ],
    {
      encoding: "utf8",
      timeout: 120_000,
      env: cleanEnv({
        SURFSENSE_TEST_SCRIPT: INSTALL_PS1,
        SURFSENSE_INSTALL_DRY_RUN: "1",
        SURFSENSE_FAKE_LATEST: "v2.2.4",
        SURFSENSE_FAKE_OS: "Windows",
        ...vars,
      }),
    }
  )
  return withSteps(result)
}

function withSteps(result) {
  const out = `${result.stdout ?? ""}${result.stderr ?? ""}`.replaceAll("\r\n", "\n")
  const steps = (prefix) =>
    out
      .split("\n")
      .filter((line) => line.startsWith(`  ${prefix}`))
      .map((line) => line.slice(prefix.length + 2))
  return {
    status: result.status,
    out,
    lines: out.split("\n"),
    downloads: steps("would download "),
    runs: steps("would run: "),
  }
}

/** Every download comes from one release tag, so SHA256SUMS always matches the file. */
function assertOneTag(plan, tag, files) {
  assert.deepEqual(
    plan.downloads,
    files.map((file) => `${RELEASE}${tag}/${file}`)
  )
}

function indexOfLine(plan, pattern) {
  const index = plan.lines.findIndex((line) => pattern.test(line))
  assert.notEqual(index, -1, `no line matches ${pattern}\n${plan.out}`)
  return index
}

const MAC = { SURFSENSE_FAKE_OS: "Darwin", SURFSENSE_FAKE_ARCH: "arm64" }
const LINUX = { SURFSENSE_FAKE_OS: "Linux", SURFSENSE_FAKE_ARCH: "x86_64" }

const shTest = (name, fn) =>
  test(name, { skip: SHELLS.length === 0 && "no POSIX shell on this machine" }, fn)
const psTest = (name, fn) =>
  test(name, { skip: POWERSHELLS.length === 0 && "no PowerShell on this machine" }, fn)

shTest("install.sh parses in every POSIX shell on this machine", () => {
  for (const shell of SHELLS) {
    const result = spawnSync(shell, ["-n", INSTALL_SH], { encoding: "utf8" })
    assert.equal(result.status, 0, `${shell}: ${result.stderr}`)
  }
})

shTest("a Mac on Apple Silicon gets the zip, accepted by Gatekeeper before it reaches /Applications", () => {
  const plan = shPlan({ ...MAC, SURFSENSE_FAKE_APPLICATIONS_WRITABLE: "1" })
  assert.equal(plan.status, 0, plan.out)
  assertOneTag(plan, "v2.2.4", ["SHA256SUMS", "SurfSense-arm64.zip"])
  const checked = indexOfLine(plan, /would check SurfSense-arm64\.zip against SHA256SUMS/)
  const unpacked = indexOfLine(plan, /would run: ditto -x -k \S+\/SurfSense-arm64\.zip \/Applications\//)
  const assessed = indexOfLine(plan, /would run: spctl --assess --type execute .*SurfSense\.app$/)
  const placed = indexOfLine(plan, /would run: mv \S+\/SurfSense\.app \/Applications\/SurfSense\.app$/)
  assert.ok(checked < unpacked && unpacked < assessed && assessed < placed, plan.out)
  assert.doesNotMatch(plan.out, /sudo/)
})

shTest("a Mac whose /Applications is not writable installs to ~/Applications without sudo", () => {
  const plan = shPlan({ ...MAC, SURFSENSE_FAKE_APPLICATIONS_WRITABLE: "0" })
  assert.equal(plan.status, 0, plan.out)
  indexOfLine(plan, /would run: mv \S+\/SurfSense\.app \/home\/tester\/Applications\/SurfSense\.app$/)
  assert.doesNotMatch(plan.out, /sudo/)
})

shTest("an Intel Mac is refused before anything is downloaded", () => {
  const plan = shPlan({ SURFSENSE_FAKE_OS: "Darwin", SURFSENSE_FAKE_ARCH: "x86_64" })
  assert.notEqual(plan.status, 0)
  assert.match(plan.out, /Apple Silicon/)
  assert.ok(plan.out.includes(DOWNLOADS_PAGE), plan.out)
  assert.deepEqual(plan.downloads, [])
})

shTest("Linux with apt adds the signed repository and installs the package from it", () => {
  const plan = shPlan({ ...LINUX, SURFSENSE_FAKE_PKG: "apt", SURFSENSE_FAKE_APT_REPO: "1" })
  assert.equal(plan.status, 0, plan.out)
  assertOneTag(plan, "v2.2.4", ["SHA256SUMS", "surfsense-archive-keyring.gpg"])
  indexOfLine(plan, /would check surfsense-archive-keyring\.gpg against SHA256SUMS/)
  assert.ok(plan.lines.includes(`    ${APT_LINE}`), plan.out)
  const why = indexOfLine(plan, /needs root/)
  const keyring = indexOfLine(plan, /would run: sudo install -m 0644 \S+ \/usr\/share\/keyrings\/surfsense-archive-keyring\.gpg$/)
  const source = indexOfLine(plan, /would run: sudo install -m 0644 \S+\/surfsense\.list \/etc\/apt\/sources\.list\.d\/surfsense\.list$/)
  const update = indexOfLine(plan, /would run: sudo apt-get update$/)
  const install = indexOfLine(plan, /would run: sudo apt-get install -y surfsense-local-electron$/)
  assert.ok(why < keyring && keyring < source && source < update && update < install, plan.out)
})

shTest("Linux with apt installs the release's .deb when the tag carries no apt repository", () => {
  const plan = shPlan({ ...LINUX, SURFSENSE_FAKE_PKG: "apt", SURFSENSE_FAKE_APT_REPO: "0" })
  assert.equal(plan.status, 0, plan.out)
  assertOneTag(plan, "v2.2.4", ["SHA256SUMS", "SurfSense.deb"])
  const why = indexOfLine(plan, /needs root/)
  const install = indexOfLine(plan, /would run: sudo apt-get install -y \S+\/SurfSense\.deb$/)
  assert.ok(why < install)
  assert.doesNotMatch(plan.out, /sources\.list\.d|--allow-downgrades/)
})

shTest("SURFSENSE_APT_REPO=0 installs the .deb and leaves apt's sources alone", () => {
  const plan = shPlan({ SURFSENSE_APT_REPO: "0", ...LINUX, SURFSENSE_FAKE_PKG: "apt", SURFSENSE_FAKE_APT_REPO: "1" })
  assert.equal(plan.status, 0, plan.out)
  assertOneTag(plan, "v2.2.4", ["SHA256SUMS", "SurfSense.deb"])
  assert.doesNotMatch(plan.out, /sources\.list\.d|keyrings/)
})

shTest("a pinned SURFSENSE_VERSION installs that tag's .deb, since the repository serves only the latest", () => {
  const plan = shPlan({ SURFSENSE_VERSION: "2.2.2", ...LINUX, SURFSENSE_FAKE_PKG: "apt", SURFSENSE_FAKE_APT_REPO: "1" })
  assert.equal(plan.status, 0, plan.out)
  assertOneTag(plan, "v2.2.2", ["SHA256SUMS", "SurfSense.deb"])
  assert.doesNotMatch(plan.out, /sources\.list\.d/)
})

shTest("a pinned SURFSENSE_VERSION may be older than the installed one, so each package manager is let downgrade", () => {
  // apt -y refuses a downgrade and zypper skips one with exit 0; dnf installs an exact local rpm either way.
  for (const [vars, command] of [
    [{ SURFSENSE_FAKE_PKG: "apt" }, /would run: sudo apt-get install -y --allow-downgrades \S+\/SurfSense\.deb$/],
    [{ SURFSENSE_FAKE_PKG: "apt", SURFSENSE_APT_REPO: "0" }, /would run: sudo apt-get install -y --allow-downgrades \S+\/SurfSense\.deb$/],
    [{ SURFSENSE_FAKE_PKG: "dnf" }, /would run: sudo dnf install -y \S+\/SurfSense\.rpm$/],
    [
      { SURFSENSE_FAKE_PKG: "zypper" },
      /would run: sudo zypper --non-interactive install --allow-unsigned-rpm --oldpackage \S+\/SurfSense\.rpm$/,
    ],
  ]) {
    const plan = shPlan({ SURFSENSE_VERSION: "2.2.2", ...LINUX, ...vars })
    assert.equal(plan.status, 0, plan.out)
    indexOfLine(plan, command)
  }
})

shTest("dnf and zypper install the release's rpm", () => {
  for (const [pkg, command] of [
    ["dnf", /would run: sudo dnf install -y \S+\/SurfSense\.rpm$/],
    ["zypper", /would run: sudo zypper --non-interactive install --allow-unsigned-rpm \S+\/SurfSense\.rpm$/],
  ]) {
    const plan = shPlan({ ...LINUX, SURFSENSE_FAKE_PKG: pkg })
    assert.equal(plan.status, 0, plan.out)
    assertOneTag(plan, "v2.2.4", ["SHA256SUMS", "SurfSense.rpm"])
    assert.ok(indexOfLine(plan, /needs root/) < indexOfLine(plan, command), plan.out)
    assert.doesNotMatch(plan.out, /--oldpackage|--allow-downgrades/)
  }
})

shTest("an image-based Linux gets the AppImage, since its package manager cannot install there", () => {
  // Bazzite, Bluefin and Aurora (ostree) carry dnf; openSUSE Aeon and MicroOS carry zypper.
  for (const pkg of ["apt", "dnf", "zypper"]) {
    const plan = shPlan({ ...LINUX, SURFSENSE_FAKE_PKG: pkg, SURFSENSE_FAKE_IMAGE_BASED: "1" })
    assert.equal(plan.status, 0, plan.out)
    assertOneTag(plan, "v2.2.4", ["SHA256SUMS", "SurfSense.AppImage"])
    assert.match(plan.out, /image-based/)
    indexOfLine(plan, /would run: mv \S+\/SurfSense\.AppImage \/home\/tester\/Applications\/SurfSense\.AppImage$/)
    assert.doesNotMatch(plan.out, /sudo/)
  }
})

shTest("a read-only root is image-based whatever is on PATH, and a writable one is not", () => {
  // openSUSE Aeon keeps transactional-update in /usr/sbin, which an ordinary
  // user's PATH lacks, and ABRoot (Vanilla OS) has none; none is on this PATH.
  // The last / in /proc/mounts is the one in effect.
  const mounts = (...roots) =>
    [
      ...roots.map((options, index) => `/dev/vda${index + 2} / btrfs ${options},relatime,subvol=/@/.snapshots/1/snapshot 0 0`),
      "/dev/vda3 /var btrfs rw,relatime,subvol=/@/var 0 0",
      "tmpfs /run tmpfs rw,nosuid,nodev 0 0",
    ].join("\n")
  const detected = { ...LINUX, SURFSENSE_FAKE_IMAGE_BASED: undefined, SURFSENSE_FAKE_OSTREE_BOOTED: "0" }
  for (const [vars, imageBased] of [
    [{ SURFSENSE_FAKE_PKG: "zypper", SURFSENSE_FAKE_MOUNTS: mounts("ro") }, true],
    [{ SURFSENSE_FAKE_PKG: "apt", SURFSENSE_FAKE_MOUNTS: mounts("rw", "ro") }, true],
    [{ SURFSENSE_FAKE_PKG: "zypper", SURFSENSE_FAKE_MOUNTS: mounts("rw") }, false],
    // A live system's writable overlay over its read-only image.
    [{ SURFSENSE_FAKE_PKG: "apt", SURFSENSE_FAKE_MOUNTS: mounts("ro", "rw") }, false],
    [{ SURFSENSE_FAKE_PKG: "dnf", SURFSENSE_FAKE_MOUNTS: mounts("rw"), SURFSENSE_FAKE_OSTREE_BOOTED: "1" }, true],
  ]) {
    const plan = shPlan({ ...detected, ...vars })
    const which = JSON.stringify(vars)
    assert.equal(plan.status, 0, plan.out)
    if (imageBased) {
      assert.match(plan.out, /image-based/, which)
      assertOneTag(plan, "v2.2.4", ["SHA256SUMS", "SurfSense.AppImage"])
      assert.doesNotMatch(plan.out, /sudo/, which)
    } else {
      assert.doesNotMatch(plan.out, /image-based/, which)
      indexOfLine(plan, new RegExp(`would run: sudo ${vars.SURFSENSE_FAKE_PKG === "apt" ? "apt-get" : "zypper"} `))
    }
  }
})

shTest("apt, dnf or zypper is used only where its own package database holds the system's C library", () => {
  // Arch may carry apt or dnf for mkosi, which would otherwise add another distribution's repository.
  for (const [onPath, libcDb, command] of [
    ["apt-get dnf", "none", null],
    ["apt-get dnf zypper", "rpm", /would run: sudo dnf install -y \S+\/SurfSense\.rpm$/],
    ["apt-get zypper", "rpm", /would run: sudo zypper --non-interactive install --allow-unsigned-rpm \S+\/SurfSense\.rpm$/],
    ["apt-get dnf", "dpkg", /would run: sudo apt-get install -y surfsense-local-electron$/],
    ["dnf zypper", "dpkg", null],
    ["none", "dpkg", null],
  ]) {
    const plan = shPlan({ ...LINUX, SURFSENSE_FAKE_ON_PATH: onPath, SURFSENSE_FAKE_LIBC_DB: libcDb })
    assert.equal(plan.status, 0, plan.out)
    if (command) {
      indexOfLine(plan, command)
    } else {
      assertOneTag(plan, "v2.2.4", ["SHA256SUMS", "SurfSense.AppImage"])
      assert.doesNotMatch(plan.out, /sudo/, `${onPath} ${libcDb}`)
    }
  }
})

shTest("Linux below glibc 2.35, or without glibc, is refused before anything is downloaded", () => {
  for (const pkg of ["apt", "dnf", "none"]) {
    for (const [glibc, has] of [
      ["2.34", "glibc 2.34"],
      ["2.31", "glibc 2.31"],
      ["2.4", "glibc 2.4"],
      ["none", "no glibc"],
    ]) {
      const plan = shPlan({ ...LINUX, SURFSENSE_FAKE_PKG: pkg, SURFSENSE_FAKE_GLIBC: glibc })
      assert.notEqual(plan.status, 0, `${pkg} ${glibc}`)
      assert.match(plan.out, /needs glibc 2\.35 or later/, plan.out)
      assert.ok(plan.out.includes(`this machine has ${has}.`), plan.out)
      assert.ok(plan.out.includes(DOWNLOADS_PAGE), plan.out)
      assert.deepEqual(plan.downloads, [], `${pkg} ${glibc}`)
    }
  }
})

shTest("glibc 2.35 and later pass the Linux floor", () => {
  for (const glibc of ["2.35", "2.36", "2.40", "3.0"]) {
    const plan = shPlan({ ...LINUX, SURFSENSE_FAKE_PKG: "none", SURFSENSE_FAKE_GLIBC: glibc })
    assert.equal(plan.status, 0, `${glibc}: ${plan.out}`)
    assertOneTag(plan, "v2.2.4", ["SHA256SUMS", "SurfSense.AppImage"])
  }
})

shTest("Linux with no supported package manager gets the AppImage and a menu entry, without sudo", () => {
  const plan = shPlan({ ...LINUX, SURFSENSE_FAKE_PKG: "none" })
  assert.equal(plan.status, 0, plan.out)
  assertOneTag(plan, "v2.2.4", ["SHA256SUMS", "SurfSense.AppImage"])
  indexOfLine(plan, /would run: mv \S+\/SurfSense\.AppImage \/home\/tester\/Applications\/SurfSense\.AppImage$/)
  indexOfLine(plan, /would write \/home\/tester\/\.local\/share\/applications\/surfsense-appimage\.desktop:$/)
  assert.ok(plan.lines.includes('    Exec="/home/tester/Applications/SurfSense.AppImage" %U'), plan.out)
  assert.doesNotMatch(plan.out, /sudo/)
})

shTest("ARM Linux and other systems are refused with the downloads page", () => {
  for (const [os, arch] of [
    ["Linux", "aarch64"],
    ["FreeBSD", "amd64"],
    ["MINGW64_NT-10.0-26100", "x86_64"],
  ]) {
    const plan = shPlan({ SURFSENSE_FAKE_OS: os, SURFSENSE_FAKE_ARCH: arch, SURFSENSE_FAKE_PKG: "apt" })
    assert.notEqual(plan.status, 0, `${os} ${arch}`)
    assert.ok(plan.out.includes(DOWNLOADS_PAGE), plan.out)
    assert.deepEqual(plan.downloads, [])
  }
})

shTest("a SURFSENSE_VERSION that is not a release number is refused", () => {
  for (const version of ["2.2", "latest", "2.2.4-beta.1", "2.2.4;id", "2.2.4\nv1.0.0"]) {
    const plan = shPlan({ SURFSENSE_VERSION: version, ...LINUX, SURFSENSE_FAKE_PKG: "none" })
    assert.notEqual(plan.status, 0, version)
    assert.match(plan.out, /SURFSENSE_VERSION must be a release number/, version)
    assert.deepEqual(plan.downloads, [], version)
  }
})

psTest("install.ps1 parses in each PowerShell here and never calls exit, which would close the window iex runs in", () => {
  const check = [
    "$tokens = $null; $errors = $null",
    "$ast = [System.Management.Automation.Language.Parser]::ParseFile($env:SURFSENSE_TEST_SCRIPT, [ref]$tokens, [ref]$errors)",
    "$exits = $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.ExitStatementAst] }, $true)",
    '"errors=$(@($errors).Count) exits=$(@($exits).Count)"',
    "$errors | ForEach-Object { $_.ToString() }",
  ].join("; ")
  for (const shell of POWERSHELLS) {
    const result = spawnSync(shell, ["-NoProfile", "-NonInteractive", "-Command", check], {
      encoding: "utf8",
      timeout: 60_000,
      env: cleanEnv({ SURFSENSE_TEST_SCRIPT: INSTALL_PS1 }),
    })
    assert.match(result.stdout, /^errors=0 exits=0$/m, `${shell}: ${result.stdout}${result.stderr}`)
  }
})

psTest("Windows x64 checks the installer's hash and signature before running it silently", () => {
  for (const shell of POWERSHELLS) {
    const plan = ps1Plan(shell, { SURFSENSE_FAKE_ARCH: "AMD64" })
    assertOneTag(plan, "v2.2.4", ["SHA256SUMS", "SurfSense-Setup.exe"])
    const hashed = indexOfLine(plan, /would check SurfSense-Setup\.exe against SHA256SUMS/)
    const signed = indexOfLine(plan, /would check SurfSense-Setup\.exe has a Valid Authenticode signature from CN=SurfSense/)
    const ran = indexOfLine(plan, /would run: ".*[\\/]SurfSense-Setup\.exe" \/S \(and wait\)$/)
    assert.ok(hashed < signed && signed < ran, plan.out)
    assert.doesNotMatch(plan.out, /emulation/)
    // Checked before the download and again just before the installer, which a download's minutes separate.
    const checks = plan.lines.flatMap((line, index) => (/would check SurfSense is not running$/.test(line) ? [index] : []))
    const downloaded = indexOfLine(plan, /would download /)
    assert.equal(checks.length, 2, plan.out)
    assert.ok(checks[0] < downloaded && signed < checks[1] && checks[1] < ran, plan.out)
  }
})

psTest("install.ps1 refuses while SurfSense is running, which the silent installer would close without asking", () => {
  for (const shell of POWERSHELLS) {
    const plan = ps1Plan(shell, { SURFSENSE_FAKE_ARCH: "AMD64", SURFSENSE_FAKE_RUNNING: "1" })
    assert.ok(plan.out.includes("SurfSense is running. Quit it, then run this again."), `${shell}: ${plan.out}`)
    assert.deepEqual(plan.downloads, [])
    assert.deepEqual(plan.runs, [])
  }
})

const WOW64_POWERSHELL = join(process.env.SystemRoot ?? "C:\\Windows", "SysWOW64", "WindowsPowerShell", "v1.0", "powershell.exe")

test(
  "install.ps1 finds this user's running 64-bit SurfSense.exe, from a 32-bit Windows PowerShell too",
  {
    skip:
      !(process.platform === "win32" && ["x64", "arm64"].includes(process.arch) && existsSync(WOW64_POWERSHELL)) &&
      "needs 64-bit Windows, a 64-bit Node and the 32-bit Windows PowerShell",
  },
  async () => {
    // A 32-bit PowerShell sees no Process.Path for a 64-bit process, so a check on
    // Get-Process alone missed the app there, and the silent installer closed it.
    const folder = realpathSync.native(mkdtempSync(join(tmpdir(), "surfsense-running-")))
    const exe = join(folder, "SurfSense.exe")
    try {
      linkSync(process.execPath, exe)
    } catch {
      copyFileSync(process.execPath, exe)
    }
    const app = spawn(exe, ["-e", "setTimeout(() => {}, 120_000)"], { stdio: "ignore" })
    const exited = once(app, "exit")
    try {
      await once(app, "spawn")
      const check = [
        "$tokens = $null; $errors = $null",
        "$ast = [System.Management.Automation.Language.Parser]::ParseFile($env:SURFSENSE_TEST_SCRIPT, [ref]$tokens, [ref]$errors)",
        "$definition = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Find-RunningApp' }, $true)",
        "if ($env:SURFSENSE_TEST_NO_CIM) { function Get-CimInstance { throw 'CIM is unavailable' } }",
        ". ([scriptblock]::Create($definition.Extent.Text))",
        "Find-RunningApp $env:SURFSENSE_TEST_FOLDER | ForEach-Object { 'found=' + $_ }",
        "Find-RunningApp ($env:SURFSENSE_TEST_FOLDER + '-other') | ForEach-Object { 'other=' + $_ }",
        "'checked'",
      ].join("; ")
      // Without CIM, Get-Process still serves a PowerShell as wide as the app.
      for (const [shell, noCim] of [
        [WOW64_POWERSHELL, ""],
        ...POWERSHELLS.map((name) => [name, ""]),
        ...POWERSHELLS.map((name) => [name, "1"]),
      ]) {
        const result = spawnSync(shell, ["-NoProfile", "-NonInteractive", "-Command", check], {
          encoding: "utf8",
          timeout: 120_000,
          env: cleanEnv({ SURFSENSE_TEST_SCRIPT: INSTALL_PS1, SURFSENSE_TEST_FOLDER: folder, SURFSENSE_TEST_NO_CIM: noCim }),
        })
        const lines = (result.stdout ?? "").toLowerCase().split(/\r?\n/)
        const which = `${shell}${noCim ? " without CIM" : ""}: ${result.stdout}${result.stderr}`
        assert.ok(lines.includes("checked"), which)
        assert.ok(lines.includes(`found=${exe.toLowerCase()}`), which)
        assert.ok(!lines.some((line) => line.startsWith("other=")), which)
      }
    } finally {
      app.kill()
      await exited
      rmSync(folder, { recursive: true, force: true, maxRetries: 5 })
    }
  }
)

psTest("Windows on Arm installs the x64 build and says it runs under emulation", () => {
  for (const shell of POWERSHELLS) {
    const plan = ps1Plan(shell, { SURFSENSE_FAKE_ARCH: "ARM64" })
    assert.match(plan.out, /emulation/)
    assertOneTag(plan, "v2.2.4", ["SHA256SUMS", "SurfSense-Setup.exe"])
  }
})

psTest("install.ps1 refuses 32-bit Windows, other systems and a malformed version before downloading", () => {
  for (const shell of POWERSHELLS) {
    for (const [vars, says] of [
      [{ SURFSENSE_FAKE_ARCH: "x86" }, DOWNLOADS_PAGE],
      [{ SURFSENSE_FAKE_OS: "Linux", SURFSENSE_FAKE_ARCH: "AMD64" }, "install.sh"],
      [{ SURFSENSE_FAKE_ARCH: "AMD64", SURFSENSE_VERSION: "2.2.4;calc" }, "SURFSENSE_VERSION"],
      [{ SURFSENSE_FAKE_ARCH: "AMD64", SURFSENSE_VERSION: "2.2.4\n" }, "SURFSENSE_VERSION"],
    ]) {
      const plan = ps1Plan(shell, vars)
      assert.ok(plan.out.includes(says), `${shell} ${JSON.stringify(vars)}: ${plan.out}`)
      assert.deepEqual(plan.downloads, [])
    }
  }
})

psTest("install.ps1 installs a pinned SURFSENSE_VERSION from that tag", () => {
  for (const shell of POWERSHELLS) {
    const plan = ps1Plan(shell, { SURFSENSE_FAKE_ARCH: "AMD64", SURFSENSE_VERSION: "v2.2.2" })
    assertOneTag(plan, "v2.2.2", ["SHA256SUMS", "SurfSense-Setup.exe"])
  }
})

/** UUID v5 (RFC 4122), the way electron-builder derives its NSIS GUID. */
function uuidV5(name, namespace) {
  const bytes = createHash("sha1")
    .update(Buffer.from(namespace.replaceAll("-", ""), "hex"))
    .update(name, "utf8")
    .digest()
    .subarray(0, 16)
  bytes[6] = (bytes[6] & 0x0f) | 0x50
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = bytes.toString("hex")
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join("-")
}

test("install.ps1 reads the install location from the NSIS key electron-builder writes for this appId", () => {
  // app-builder-lib's NsisTarget: options.guid || UUID.v5(appId, ELECTRON_BUILDER_NS_UUID).
  const appId = readFileSync(BUILDER_YML, "utf8").match(/^appId: (\S+)\r?$/m)?.[1]
  assert.equal(appId, "com.surfsense.app")
  const guid = uuidV5(appId, "50e065bc-3134-11e6-9bab-38c9862bdaf3")
  assert.ok(readFileSync(INSTALL_PS1, "utf8").includes(`Software\\${guid}`))
})

test("both scripts reach only the GitHub release and the downloads page: no telemetry", () => {
  for (const file of [INSTALL_SH, INSTALL_PS1]) {
    const urls = readFileSync(file, "utf8").match(/https?:\/\/[^\s"'`)]+/g) ?? []
    assert.ok(urls.length > 0, file)
    for (const url of urls) {
      assert.match(
        url,
        /^https:\/\/(github\.com\/MODSetter\/SurfSense(\/|$)|www\.surfsense\.com\/(downloads|install\.sh|install\.ps1)$)/,
        `${file}: ${url}`
      )
    }
  }
})

test("both scripts are plain ASCII, so irm on Windows PowerShell 5.1 cannot mangle them", () => {
  for (const file of [INSTALL_SH, INSTALL_PS1]) {
    const bytes = readFileSync(file)
    assert.ok(bytes.every((byte) => byte < 0x80), `${file} has a non-ASCII byte`)
  }
})

test("install.sh has LF line endings, which sh needs", () => {
  // .gitattributes pins *.sh to LF; a Windows checkout may give the .ps1 CRLF, which PowerShell reads fine.
  assert.ok(!readFileSync(INSTALL_SH).includes(0x0d))
})
