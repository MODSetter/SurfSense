// surfsense-bin for the AUR: a repackage of the release's SurfSense.deb, which
// release-channels.yml pushes on every published release.
import { downloadUrl, HOMEPAGE, LICENSE, SUMMARY } from "./listing.mjs"

const PKGNAME = "surfsense-bin"
const PKGREL = "1"
// The deb's Depends under Arch's names (gcc-libs carries libgomp, for llama.cpp),
// plus alsa-lib, which Electron links and the deb leaves to the desktop.
const DEPENDS = [
  "alsa-lib",
  "at-spi2-core",
  "gcc-libs",
  "gtk3",
  "libnotify",
  "libsecret",
  "libxss",
  "libxtst",
  "nss",
  "util-linux-libs",
  "xdg-utils",
]
// The deb's Recommends: libappindicator replaced libappindicator-gtk3 in Arch.
const OPTDEPENDS = [
  "libappindicator: tray icon on desktops that need one",
  "vulkan-icd-loader: GPU acceleration for local models, with a Vulkan driver",
]
// Stripping would break the frozen Python backend and the prebuilt model runtimes.
const OPTIONS = ["!strip", "!debug"]

const quoted = (values) => values.map((value) => `'${value}'`)

/** PKGBUILD and the .SRCINFO makepkg --printsrcinfo would write for it. */
export function aurPackage(release) {
  const { version } = release
  const deb = release.asset("SurfSense.deb")
  const source = `${PKGNAME}-${version}.deb::${deb.url}`

  const pkgbuild = `# Maintainer: SurfSense <noreply@surfsense.app>
#
# Written by surfsense_local/packaging/channels/render.mjs in MODSetter/SurfSense,
# which release-channels.yml runs on every release: change that, not this file.

pkgname=${PKGNAME}
_pkgname=surfsense
pkgver=${version}
pkgrel=${PKGREL}
pkgdesc='${SUMMARY}'
arch=('x86_64')
url='${HOMEPAGE}'
license=('${LICENSE}')
depends=(
${quoted(DEPENDS).map((name) => `  ${name}\n`).join("")})
optdepends=(
${quoted(OPTDEPENDS).map((line) => `  ${line}\n`).join("")})
provides=("\${_pkgname}=\${pkgver}")
conflicts=("\${_pkgname}")
options=(${quoted(OPTIONS).join(" ")})
source=("\${pkgname}-\${pkgver}.deb::${downloadUrl("${pkgver}", "SurfSense.deb")}")
sha256sums=('${deb.sha256}')

package() {
  # makepkg has unpacked the deb's ar archive into $srcdir.
  bsdtar -xf "\${srcdir}"/data.tar.* -C "\${pkgdir}"

  # pacman updates this install: the app reads the marker and stops updating
  # itself, and electron-updater loses its feed and its deb self-update.
  local resources="\${pkgdir}/opt/SurfSense/resources"
  rm -f "\${resources}/app-update.yml" "\${resources}/package-type"
  printf '%s\\n' aur > "\${resources}/install-channel"

  # The deb links these with update-alternatives, which pacman does not run.
  install -dm755 "\${pkgdir}/usr/bin"
  ln -s /opt/SurfSense/surfsense-local "\${pkgdir}/usr/bin/surfsense-local"
  ln -s /opt/SurfSense/surfsense-local "\${pkgdir}/usr/bin/surfsense"

  # Apache-2.0 is in Arch's licenses package; the bundled components' notices are not.
  install -dm755 "\${pkgdir}/usr/share/licenses/\${pkgname}"
  ln -s /opt/SurfSense/resources/licenses/THIRD_PARTY_NOTICES.txt \\
    "\${pkgdir}/usr/share/licenses/\${pkgname}/THIRD_PARTY_NOTICES.txt"
}
`

  const fields = [
    ["pkgdesc", SUMMARY],
    ["pkgver", version],
    ["pkgrel", PKGREL],
    ["url", HOMEPAGE],
    ["arch", "x86_64"],
    ["license", LICENSE],
    ...DEPENDS.map((name) => ["depends", name]),
    ...OPTDEPENDS.map((line) => ["optdepends", line]),
    ["provides", `surfsense=${version}`],
    ["conflicts", "surfsense"],
    ...OPTIONS.map((option) => ["options", option]),
    ["source", source],
    ["sha256sums", deb.sha256],
  ]
  const srcinfo = [
    `pkgbase = ${PKGNAME}`,
    ...fields.map(([key, value]) => `\t${key} = ${value}`),
    "",
    `pkgname = ${PKGNAME}`,
    "",
  ].join("\n")

  return { PKGBUILD: pkgbuild, ".SRCINFO": srcinfo }
}
