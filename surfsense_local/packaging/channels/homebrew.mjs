// The Homebrew cask, for a pull request to Homebrew/homebrew-cask as Casks/s/surfsense.rb.
// After the first one, BrewTestBot bumps it on its own.
import { HOMEPAGE, NAME, REPO, SUMMARY } from "./listing.mjs"

// The app's data and the updater's cache. ~/Library/Application Support/SurfSense
// belongs to the legacy 0.0.x desktop, which 2.x does not touch.
const MAC_ZAP = [
  "~/.surfsense",
  "~/Library/Caches/com.surfsense.app",
  "~/Library/Caches/com.surfsense.app.ShipIt",
  "~/Library/Caches/surfsense-local-electron-updater",
  "~/Library/HTTPStorages/com.surfsense.app",
  "~/Library/Preferences/com.surfsense.app.plist",
  "~/Library/Saved Application State/com.surfsense.app.savedState",
]
const LINUX_ZAP = ["~/.cache/surfsense-local-electron-updater", "~/.surfsense"]

const trash = (paths) => paths.map((path) => `      "${path}",\n`).join("")

/**
 * surfsense.rb for `release`. auto_updates sits in on_macos only: there brew still
 * upgrades the app while its bundle is older than the cask, which it is whenever
 * the in-app updater is off (the default); on Linux it would make plain
 * `brew upgrade` skip the AppImage, which has no bundle version to compare.
 */
export function homebrewCask(release) {
  const dmg = release.asset("SurfSense-arm64.dmg")
  const appImage = release.asset("SurfSense.AppImage")
  const cask = `cask "surfsense" do
  os macos: "-arm64.dmg", linux: ".AppImage"

  version "${release.version}"
  sha256 arm:          "${dmg.sha256}",
         x86_64_linux: "${appImage.sha256}"

  on_macos do
    auto_updates true
    depends_on arch: :arm64
    depends_on macos: :ventura

    app "SurfSense.app"

    zap trash: [
${trash(MAC_ZAP)}    ]
  end
  on_linux do
    depends_on arch: :x86_64

    app_image "SurfSense.AppImage"

    zap trash: [
${trash(LINUX_ZAP)}    ]
  end

  url "https://github.com/${REPO}/releases/download/v#{version}/SurfSense#{os}"
  name "${NAME}"
  desc "${SUMMARY}"
  homepage "${HOMEPAGE}/"

  livecheck do
    url :url
    strategy :github_latest
  end
end
`
  return { "surfsense.rb": cask }
}
