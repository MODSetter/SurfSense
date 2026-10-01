// Everything the agent's runtime is made from, pinned by version and sha256.
// opencode ships often and its server API is unversioned, so the backend speaks
// exactly this release (docs/proposals/agent/03-opencode.md).

export const VERSION = "1.18.34"
// The release opencode itself downloads when `rg` is missing; shipped so it never does.
export const RIPGREP_VERSION = "15.1.0"

const OPENCODE = `https://github.com/anomalyco/opencode/releases/download/v${VERSION}`
const RIPGREP = `https://github.com/BurntSushi/ripgrep/releases/download/${RIPGREP_VERSION}`

// The release archives carry the executable alone, so the licence comes from the tag.
export const OPENCODE_LICENCE = {
  url: `https://raw.githubusercontent.com/anomalyco/opencode/v${VERSION}/LICENSE`,
  sha256: "625f0f619133f89bbbb2abe37369613dfa1885eba1e50d02170deb62bb42cb6b", // pragma: allowlist secret
}

// x64 takes opencode's `-baseline` build, compiled with `avx2: false`, so a CPU
// without AVX2 runs it. ripgrep's Linux build is static (musl), so it needs no glibc.
export const HOSTS = {
  "darwin-arm64": {
    opencode: {
      url: `${OPENCODE}/opencode-darwin-arm64.zip`,
      sha256: "8522b70f545184b3a8d97c5ca4f814093b2476d72aebfda8c48bcd072ec31d1b", // pragma: allowlist secret
    },
    ripgrep: {
      url: `${RIPGREP}/ripgrep-${RIPGREP_VERSION}-aarch64-apple-darwin.tar.gz`,
      sha256: "378e973289176ca0c6054054ee7f631a065874a352bf43f0fa60ef079b6ba715", // pragma: allowlist secret
    },
  },
  "linux-x64": {
    opencode: {
      url: `${OPENCODE}/opencode-linux-x64-baseline.tar.gz`,
      sha256: "24b0d458d21ef548b2752166303defcf7f4945b049fb4876ab78dfaf86d81b27", // pragma: allowlist secret
    },
    ripgrep: {
      url: `${RIPGREP}/ripgrep-${RIPGREP_VERSION}-x86_64-unknown-linux-musl.tar.gz`,
      sha256: "1c9297be4a084eea7ecaedf93eb03d058d6faae29bbc57ecdaf5063921491599", // pragma: allowlist secret
    },
  },
  "win32-x64": {
    opencode: {
      url: `${OPENCODE}/opencode-windows-x64-baseline.zip`,
      sha256: "f89ab2720050780a450e3cf3e48ac3f0409235b46b6c548c69aa2b7051d716f4", // pragma: allowlist secret
    },
    ripgrep: {
      url: `${RIPGREP}/ripgrep-${RIPGREP_VERSION}-x86_64-pc-windows-msvc.zip`,
      sha256: "124510b94b6baa3380d051fdf4650eaa80a302c876d611e9dba0b2e18d87493a", // pragma: allowlist secret
    },
  },
}
