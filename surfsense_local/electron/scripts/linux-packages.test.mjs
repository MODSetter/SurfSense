import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { createRequire } from "node:module"
import { join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

const ELECTRON = fileURLToPath(new URL("..", import.meta.url))
const builder = createRequire(createRequire(import.meta.url).resolve("electron-builder"))
const appBuilder = createRequire(builder.resolve("app-builder-lib"))

/** electron-builder.yml, parsed with electron-builder's own YAML reader. */
const config = appBuilder("js-yaml").load(readFileSync(join(ELECTRON, "electron-builder.yml"), "utf8"))

/** The snapcraft.core24 options the release's snap job adds on electron-builder's command line. */
function snapJobOptions() {
  const workflow = readFileSync(join(ELECTRON, "..", "..", ".github", "workflows", "release-local.yml"), "utf8")
  const flags = [...workflow.matchAll(/-c\.snapcraft\.core24\.(\w+)=(\w+)/g)]
  // electron-builder's schema coerces "true" and "false" to booleans.
  return Object.fromEntries(flags.map(([, key, value]) => [key, value === "true" ? true : value === "false" ? false : value]))
}

/** The snapcraft.yaml electron-builder writes for the snap job, and the arguments its launcher passes. */
async function snapBuild() {
  const { LinuxTargetHelper } = builder("app-builder-lib/out/targets/LinuxTargetHelper")
  const { Arch } = builder("builder-util")
  const snapcraft = { ...config.snapcraft, core24: { ...config.snapcraft.core24, ...snapJobOptions() } }
  // The packager fields the core24 descriptor reads; the rest stays electron-builder's.
  const packager = {
    config: { ...config, snapcraft, electronVersion: createRequire(import.meta.url)("electron/package.json").version },
    platformSpecificBuildOptions: config.linux,
    executableName: config.linux.executableName,
    appInfo: { version: "2.2.4", productName: config.productName },
  }
  const helper = new LinuxTargetHelper(packager)
  Object.defineProperty(helper, "icons", { value: Promise.resolve([]) })
  const core = helper.getSnapCore()
  const snap = await core.mapSnapOptionsToSnapcraftYAML(Arch.x64)
  return { snap, args: core.commandArgs }
}

test("the AppImage uses the static type-2 runtime, so it starts without libfuse2", () => {
  assert.equal(config.toolsets?.appimage, "1.0.3")
})

test("the release packages the AppImage, the deb and the rpm; the snap has its own job", () => {
  // A snap target here would need snapcraft and a core24 build host on the release runner.
  assert.deepEqual(config.linux.target, ["AppImage", "deb", "rpm"])
})

test("the rpm requires electron-builder's libraries but libXScrnSaver, plus libgomp", () => {
  // EL10 ships libXScrnSaver only in EPEL, and Electron 44 neither links nor loads
  // libXss (measured on electron-v44.2.0-linux-x64), so the default list would refuse
  // a stock EL10 for nothing. Setting depends replaces that list, so the rest is restated.
  // llama.cpp's libraries link the host's libgomp.so.1, which its archive does not carry;
  // Fedora and EL name it libgomp, openSUSE libgomp1.
  assert.deepEqual(config.rpm?.depends, [
    "gtk3",
    "libnotify",
    "nss",
    "(libXtst or libXtst6)",
    "xdg-utils",
    "at-spi2-core",
    "(libuuid or libuuid1)",
    "(libgomp or libgomp1)",
  ])
  assert.ok(!config.rpm?.fpm?.some((arg) => arg.startsWith("--depends")))
})

test("the rpm recommends the Vulkan loader llama.cpp's GPU backend opens, as the deb does", () => {
  assert.ok(config.rpm?.fpm?.includes("--rpm-tag=Recommends: vulkan-loader"))
})

test("the snap is a strictly confined core24 build for the stable grade, named surfsense-local", async () => {
  const { snap } = await snapBuild()
  assert.equal(config.snapcraft?.base, "core24")
  assert.equal(snap.name, "surfsense-local")
  assert.equal(snap.confinement, "strict")
  assert.equal(snap.grade, "stable")
})

test("the snap job builds in LXD, so the snap keeps electron-builder's GNOME extension", async () => {
  // Destructive mode drops the extension, and with it GTK, Mesa and the fonts.
  assert.deepEqual(snapJobOptions(), { useLXD: true })
  const { snap } = await snapBuild()
  assert.deepEqual(snap.apps["surfsense-local"].extensions, ["gnome"])
  // snapcraft's extension then adds the gnome-46-2404, theme and gpu-2404 content
  // plugs and their layout, so electron-builder writes no root plugs or layout to clash.
  assert.equal(snap.plugs, undefined)
  assert.equal(snap.layout, undefined)
})

test("electron-builder never uploads the snap to the Snap Store itself", () => {
  // Without a publish entry of its own, a snap build with --publish falls back to `snapcraft upload`.
  const { default: SnapTarget } = builder("app-builder-lib/out/targets/snap/SnapTarget")
  const packager = { config, platformSpecificBuildOptions: config.linux }
  const target = new SnapTarget("snap", packager, null, ELECTRON)
  assert.equal(config.snapcraft?.publish?.provider, "github")
  assert.equal(target.findSnapPublishConfig(config), null)
})

test("the snap leaves Chromium's sandbox to confinement, so it needs no allow-sandbox review", async () => {
  const { snap, args } = await snapBuild()
  const sandboxed = Object.values(snap.plugs ?? {}).filter((plug) => plug?.["allow-sandbox"])
  assert.deepEqual(sandboxed, [])
  assert.ok(args.includes("--no-sandbox"))
})

test("the snap may serve the local API, use the microphone and read the home folder", async () => {
  const { snap } = await snapBuild()
  const plugs = snap.apps["surfsense-local"].plugs
  for (const plug of ["browser-support", "network", "network-bind", "audio-record", "home"]) {
    assert.ok(plugs.includes(plug), plug)
  }
})

test("the snap stages libgomp1 for llama.cpp and the Vulkan loader, beside electron-builder's own", async () => {
  const { snap } = await snapBuild()
  const staged = snap.parts["surfsense-local"]["stage-packages"]
  for (const pkg of ["libgomp1", "libvulkan1", "libnss3"]) assert.ok(staged.includes(pkg), pkg)
})
