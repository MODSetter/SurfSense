// The installers against a stand-in docker: what each run writes, pulls and says.
// node --test docker/scripts/install.test.ts; install.ps1's half needs pwsh.

import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { chmodSync, cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { delimiter, join, resolve } from "node:path"
import { pathToFileURL } from "node:url"
import { afterEach, beforeEach, describe, test } from "node:test"

const REPO = resolve(import.meta.dirname, "../..")
const LEGACY_COMPOSE = "name: surfsense\nservices:\n  backend:\n    image: ghcr.io/modsetter/surfsense-backend:latest\n"

// Answers what the installers ask, from files in its folder, and logs every call.
const FAKE_DOCKER = `#!/usr/bin/env bash
here="$(dirname "$0")"
echo "$PWD :: $*" >> "$here/calls.log"
flag() { [[ -f "$here/$1" ]]; }
case "$*" in
  "info") flag down && exit 1; exit 0 ;;
  "info --format {{.Architecture}}") cat "$here/arch" 2>/dev/null || echo x86_64 ;;
  "compose version") exit 0 ;;
  ps\\ -aq\\ *) flag found && echo c0ffee; exit 0 ;;
  ps\\ *) cat "$here/found" 2>/dev/null; exit 0 ;;
  "inspect c0ffee") printf '[{"Config":{"Labels":{"com.docker.compose.project.working_dir":"%s"}}}]' "$(cat "$here/found")" ;;
  "compose config --images") echo ghcr.io/modsetter/surfsense:latest ;;
  image\\ inspect\\ *) flag image-id && cat "$here/image-id" || exit 1 ;;
  "compose pull") flag pull-fails && exit 1; flag next-id && cp "$here/next-id" "$here/image-id"; exit 0 ;;
  compose\\ up\\ *) flag up-fails && exit 1; exit 0 ;;
  "compose exec -T surfsense cat /app/VERSION") echo 2.4.0 ;;
  compose\\ logs\\ *) echo "the container's last lines" ;;
  image\\ rm\\ *) exit 0 ;;
  *) echo "unexpected: $*" >&2; exit 2 ;;
esac
`

type Run = { status: number | null; out: string }

let work: string
let bin: string
let source: string

function set(name: string, value = ""): void {
  writeFileSync(join(bin, name), value)
}

function calls(): string[] {
  const log = join(bin, "calls.log")
  return existsSync(log) ? readFileSync(log, "utf8").trim().split("\n") : []
}

beforeEach(() => {
  work = mkdtempSync(join(tmpdir(), "surfsense-install-"))
  bin = join(work, "bin")
  source = join(work, "source")
  mkdirSync(bin)
  writeFileSync(join(bin, "docker"), FAKE_DOCKER)
  chmodSync(join(bin, "docker"), 0o755)
  mkdirSync(join(source, "docker/surfsense"), { recursive: true })
  for (const file of ["docker-compose.yml", ".env.example"]) {
    cpSync(join(REPO, "docker/surfsense", file), join(source, "docker/surfsense", file))
  }
  mkdirSync(join(work, "cwd"))
})

afterEach(() => rmSync(work, { recursive: true, force: true }))

// Resolved once, so a test can run it with a PATH that has no docker.
function which(command: string): string {
  return spawnSync("sh", ["-c", `command -v ${command}`], { encoding: "utf8" }).stdout.trim()
}

const BASH = which("bash")
const PWSH = which("pwsh")

const INSTALLERS = [
  {
    name: "install.sh",
    available: true,
    run: (cwd: string, path: string): Run => runIn(BASH, [join(REPO, "docker/scripts/install.sh")], cwd, path),
  },
  {
    name: "install.ps1",
    available: PWSH !== "",
    run: (cwd: string, path: string): Run =>
      runIn(PWSH, ["-NoProfile", "-NonInteractive", "-File", join(REPO, "docker/scripts/install.ps1")], cwd, path),
  },
]

function runIn(command: string, args: string[], cwd: string, path: string): Run {
  const result = spawnSync(command, args, {
    cwd,
    encoding: "utf8",
    env: { ...process.env, PATH: path, SURFSENSE_INSTALL_SOURCE: pathToFileURL(source).href },
  })
  return { status: result.status, out: result.stdout + result.stderr }
}

for (const installer of INSTALLERS) {
  describe(installer.name, { skip: !installer.available && "pwsh is not installed" }, () => {
    const run = (cwd = join(work, "cwd")): Run => installer.run(cwd, `${bin}${delimiter}${process.env.PATH}`)
    const install = (): string => join(work, "cwd", "surfsense")

    test("a first run installs into ./surfsense, starts it and says a password comes next", () => {
      const { status, out } = run()
      assert.equal(status, 0, out)
      assert.equal(readFileSync(join(install(), ".env"), "utf8"), readFileSync(join(source, "docker/surfsense/.env.example"), "utf8"))
      assert.ok(existsSync(join(install(), "docker-compose.yml")))
      assert.ok(calls().some((call) => call.endsWith(":: compose pull")))
      assert.ok(calls().some((call) => call.includes("compose up -d --wait")))
      assert.match(out, /SurfSense 2\.4\.0 is running/)
      assert.match(out, /localhost:4929/)
      assert.match(out, /first visit asks you to create a password/)
    })

    test("a second run keeps .env, replaces the compose file and removes the image it replaced", () => {
      run()
      writeFileSync(join(install(), ".env"), "SURFSENSE_PORT=5000\n")
      writeFileSync(join(install(), "docker-compose.yml"), "name: surfsense\nservices:\n  surfsense:\n    image: old\n")
      set("image-id", "sha256:old")
      set("next-id", "sha256:new")
      const { status, out } = run()
      assert.equal(status, 0, out)
      assert.equal(readFileSync(join(install(), ".env"), "utf8"), "SURFSENSE_PORT=5000\n")
      assert.equal(
        readFileSync(join(install(), "docker-compose.yml"), "utf8"),
        readFileSync(join(source, "docker/surfsense/docker-compose.yml"), "utf8"),
      )
      assert.ok(calls().some((call) => call.endsWith(":: image rm sha256:old")))
      assert.match(out, /SurfSense updated to 2\.4\.0/)
      assert.match(out, /localhost:5000/)
      assert.doesNotMatch(out, /create a password/)
    })

    test("a second run with no newer image says it is up to date and removes nothing", () => {
      run()
      set("image-id", "sha256:same")
      const { status, out } = run()
      assert.equal(status, 0, out)
      assert.match(out, /already up to date/)
      assert.ok(!calls().some((call) => call.includes("image rm")))
    })

    test("reads .env as Compose does: inline comments, quotes and Windows line ends", () => {
      run()
      writeFileSync(join(install(), ".env"), 'SURFSENSE_PORT=5000 # mine\r\nSURFSENSE_VERSION="latest"\r\n')
      const { out } = run()
      assert.match(out, /http:\/\/localhost:5000\s/)
      assert.doesNotMatch(out, /# mine|\r|Pinned/)
    })

    test("a pinned version says how to update past it", () => {
      run()
      writeFileSync(join(install(), ".env"), "SURFSENSE_VERSION=2.3.0\n")
      const { out } = run()
      assert.match(out, /Pinned to 2\.3\.0/)
    })

    test("run from another folder, it updates the install its container names", () => {
      run()
      set("found", install())
      const elsewhere = join(work, "elsewhere")
      mkdirSync(elsewhere)
      const { status, out } = run(elsewhere)
      assert.equal(status, 0, out)
      assert.ok(!existsSync(join(elsewhere, "surfsense")))
      assert.match(out, /already up to date|updated/)
    })

    test("a ./surfsense holding something else is left alone", () => {
      mkdirSync(install())
      writeFileSync(join(install(), "docker-compose.yml"), LEGACY_COMPOSE)
      writeFileSync(join(install(), ".env"), "SURFSENSE_VARIANT=cuda\n")
      const { status, out } = run()
      assert.notEqual(status, 0)
      assert.match(out, /already holds something else/)
      assert.equal(readFileSync(join(install(), "docker-compose.yml"), "utf8"), LEGACY_COMPOSE)
      assert.ok(!calls().some((call) => call.includes("compose pull")))
    })

    test("stops before writing anything when Docker is not running", () => {
      set("down")
      const { status, out } = run()
      assert.notEqual(status, 0)
      assert.match(out, /Docker is not running/)
      assert.ok(!existsSync(install()))
    })

    test("stops on a server that is not x86-64", () => {
      set("arch", "aarch64")
      const { status, out } = run()
      assert.notEqual(status, 0)
      assert.match(out, /x86-64 \(amd64\) servers only/)
      assert.ok(!existsSync(install()))
    })

    test("stops when Docker is not installed", () => {
      const empty = join(work, "empty")
      mkdirSync(empty)
      const { status, out } = installer.run(join(work, "cwd"), empty)
      assert.notEqual(status, 0)
      assert.match(out, /Docker is not installed/)
    })

    test("a container that never gets ready shows its logs", () => {
      set("up-fails")
      const { status, out } = run()
      assert.notEqual(status, 0)
      assert.match(out, /the container's last lines/)
      assert.match(out, /SurfSense didn't start/)
    })
  })
}

