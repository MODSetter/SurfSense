# Release — plugin directory site

> Owns: the `directory_site/` job in `plugins/bundles/core/cli/surfsense_plugin_cli/`, `.github/workflows/plugins-directory-site.yml`, the `gh-pages` branch of `SurfSense-Inc/surfsense-plugin-releases`.
> Reads: the live catalog ([`../01-protocol.md`](../01-protocol.md#catalog)). Written with: the GitHub App of [`03-publishing.md`](03-publishing.md).

## Goal

One public page answers what plugins exist, what each does, what it needs, whether a version is blocked, and how often it is downloaded, without anyone browsing release pages or editing a page by hand.

## Work

- `surfsense-plugins build-directory-site` turns the live catalog, and GitHub's download counts for the files in `SurfSense-Inc/surfsense-plugin-releases`, into a static site. The counts come from the REST API, where every release file reports its `download_count`.
- The site is served by GitHub Pages from the `gh-pages` branch of `surfsense-plugin-releases`, at `https://surfsense-inc.github.io/surfsense-plugin-releases/`. This repository's own Pages site renders the project README and is left alone.
- **Index page**, one row per plugin: name, description, author, `free` or `paid`, newest version and "needs SurfSense X or newer", platforms, the hosts it contacts, the secrets it asks for, downloads, and whether any version is blocked. The hosts come first among the details, since for a privacy product they are what a user most needs to know before installing.
- **A page per plugin**: every version with the SurfSense release it shipped with, downloads per version and per platform, each block with its reason and the apps it applies to, and a link to the plugin's folder in this repository.
- **A page per SurfSense release**: the plugins it published, and the versions it blocked.
- `plugins-directory-site.yml` runs after `go-live` and after `withdraw`, and once a day so the counts stay current. It commits the built site to `gh-pages` with the App's token.
- The site is plain static HTML: no script from a third party, no analytics and no cookies. The counts are GitHub's own; the app sends nothing to build them.
- Homebrew's package browser, formulae.brew.sh, is built the same way: a workflow turns its JSON data into HTML and deploys it to GitHub Pages.

## Acceptance

- After a release goes live, the index lists every plugin in the live catalog with its newest version, and each plugin page lists every version.
- A plugin's download count equals the sum of its files' `download_count` values.
- A blocked version shows its reason and the apps it applies to.
- The built site loads no resource from outside `surfsense-inc.github.io`.
- Running the workflow twice with nothing changed commits nothing the second time.

## Needs from

A live catalog from [`03-publishing.md`](03-publishing.md), and the App's token.
