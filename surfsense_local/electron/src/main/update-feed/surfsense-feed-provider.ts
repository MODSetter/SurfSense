import { Provider, type ResolvedUpdateFileInfo, type UpdateInfo } from "electron-updater"
import {
  resolveFiles,
  type ProviderRuntimeOptions,
} from "electron-updater/out/providers/Provider.js"

import { feedBase, githubReleaseDownload } from "./feed-addresses.ts"
import { latestManifest, type UpdateFeed } from "./latest-manifest.ts"

type FeedProviderOptions = { provider: "custom"; feed: UpdateFeed }

/** What AppUpdater.setFeedURL takes to use this provider. */
export type SurfSenseFeedOptions = FeedProviderOptions & {
  updateProvider: typeof SurfSenseFeedProvider
}

export function surfSenseFeedOptions(feed: UpdateFeed): SurfSenseFeedOptions {
  return { provider: "custom", updateProvider: SurfSenseFeedProvider, feed }
}

/**
 * electron-updater's custom provider (providerFactory.js "custom"): the signed
 * manifest from GitHub or an admin's mirror, and the installer from the release
 * its version names, or from the mirror. electron-updater checks each download
 * against the manifest's sha512, so the signature vouches for the installer too.
 */
export class SurfSenseFeedProvider extends Provider<UpdateInfo> {
  private readonly feed: UpdateFeed

  constructor(
    options: FeedProviderOptions,
    _updater: unknown,
    runtimeOptions: ProviderRuntimeOptions
  ) {
    // One range per request, as GitHubProvider asks: the installers download from
    // GitHub's release CDN, which answers a multi-range request with 501, so every
    // differential update would fall back to the whole installer.
    super({ ...runtimeOptions, isUseMultipleRangeRequest: false })
    this.feed = options.feed
  }

  // AppUpdater hands every provider the install ID (x-user-staging-id) here. This
  // one sends only the headers it was built with, so the ID never leaves.
  override setRequestHeaders(_ignored: unknown): void {}

  getLatestVersion(): Promise<UpdateInfo> {
    return latestManifest(this.feed)
  }

  // GitHub's are names on the version's own release, not Latest's: a release that
  // carries an earlier Windows build's release.yml forward points at that build.
  resolveFiles(updateInfo: UpdateInfo): ResolvedUpdateFileInfo[] {
    const base = this.feed.mirror
      ? feedBase(this.feed.base)
      : githubReleaseDownload(updateInfo.version)
    return resolveFiles(updateInfo, new URL(base))
  }
}
