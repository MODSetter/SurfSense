// Everything the agent's runtime is made from, pinned by version and sha256.
// opencode ships often and its server API is unversioned, so the backend speaks
// exactly this release (docs/architecture/packaging.md).

export const VERSION = "2.1.2"
// The release opencode itself downloads when `rg` is missing; shipped so it never does.
export const RIPGREP_VERSION = "15.1.0"

// 2.x is published on npm only: one package per platform, holding the executable alone.
const OPENCODE = "https://registry.npmjs.org/@opencode"
const RIPGREP = `https://github.com/BurntSushi/ripgrep/releases/download/${RIPGREP_VERSION}`

// The packages carry the executable alone, so the licence comes from the tag.
export const OPENCODE_LICENCE = {
  url: `https://raw.githubusercontent.com/anomalyco/opencode/v${VERSION}/LICENSE`,
  sha256: "625f0f619133f89bbbb2abe37369613dfa1885eba1e50d02170deb62bb42cb6b", // pragma: allowlist secret
}

// x64 takes opencode's `-baseline` build, compiled with `avx2: false`, so a CPU
// without AVX2 runs it; Linux's needs glibc 2.30 or later. ripgrep's Linux build is
// static (musl), so it needs no glibc.
export const HOSTS = {
  "darwin-arm64": {
    opencode: {
      url: `${OPENCODE}/cli-darwin-arm64/-/cli-darwin-arm64-${VERSION}.tgz`,
      sha256: "88e5fa8d8e29354308350c5ed7842e23f63c0b4e4594cd8f91b0ca006b7da224", // pragma: allowlist secret
    },
    ripgrep: {
      url: `${RIPGREP}/ripgrep-${RIPGREP_VERSION}-aarch64-apple-darwin.tar.gz`,
      sha256: "378e973289176ca0c6054054ee7f631a065874a352bf43f0fa60ef079b6ba715", // pragma: allowlist secret
    },
  },
  "linux-x64": {
    opencode: {
      url: `${OPENCODE}/cli-linux-x64-baseline/-/cli-linux-x64-baseline-${VERSION}.tgz`,
      sha256: "e8a87dc3dba4acbd931b575db4d62722b66e13df5b208f73a8a9da69fdcacdc6", // pragma: allowlist secret
    },
    ripgrep: {
      url: `${RIPGREP}/ripgrep-${RIPGREP_VERSION}-x86_64-unknown-linux-musl.tar.gz`,
      sha256: "1c9297be4a084eea7ecaedf93eb03d058d6faae29bbc57ecdaf5063921491599", // pragma: allowlist secret
    },
  },
  "win32-x64": {
    opencode: {
      url: `${OPENCODE}/cli-windows-x64-baseline/-/cli-windows-x64-baseline-${VERSION}.tgz`,
      sha256: "a3f55a44492671cad2f464d901f4a264de0f13bdae68e55b2a3ac09424268494", // pragma: allowlist secret
    },
    ripgrep: {
      url: `${RIPGREP}/ripgrep-${RIPGREP_VERSION}-x86_64-pc-windows-msvc.zip`,
      sha256: "124510b94b6baa3380d051fdf4650eaa80a302c876d611e9dba0b2e18d87493a", // pragma: allowlist secret
    },
  },
}
