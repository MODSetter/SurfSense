// The Ed25519 keys release*.yml must be signed by (ADR 0091), raw 32 bytes in hex,
// never read from configuration, environment or disk. The primary signs in CI; the
// backup stays offline. Changing this list strands every app that trusts neither.
export const UPDATE_PUBLIC_KEYS_HEX: readonly string[] = [
  // primary
  "c6b2f835406fa5a43ada7c7bb91a3b2974633e22fe232ed7c6a91c430fb39d9e", // pragma: allowlist secret
  // backup
  "0f7e78eb7fe998e1230a60e5849927c9de9ecd10470ac004b9212cc2be13c876", // pragma: allowlist secret
]
