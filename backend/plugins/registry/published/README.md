# published/

Written by CI only. Do not edit.

On every merge to `dev` that changes `../plugins.json` or `../icons/`, the sign job in [`plugins-registry.yml`](../../../../.github/workflows/plugins-registry.yml) writes `plugins.json` here, stamped with `generated_at` and each icon's `icon_sha256`, and `plugins.json.sig`, its Ed25519 signature. The registry container serves these two files. A pull request that edits this folder fails its checks.
