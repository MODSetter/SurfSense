# SurfSense (legacy)

This branch is the self-hosted SurfSense stack, frozen at the version in [`VERSION`](VERSION). It gets bug fixes only.

The SurfSense desktop app is on [`main`](https://github.com/MODSetter/SurfSense/tree/main).

## Install

Linux and macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/MODSetter/SurfSense/legacy/docker/scripts/install.sh | bash
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/MODSetter/SurfSense/legacy/docker/scripts/install.ps1 | iex
```

The installer pulls `ghcr.io/modsetter/surfsense-backend`, `surfsense-web` and `surfsense-sandbox`, and opens on the login page.

## Trees

| Tree | Role |
|------|------|
| [`surfsense_backend`](surfsense_backend) | FastAPI API |
| [`surfsense_web`](surfsense_web) | Next.js UI |
| [`surfsense_mcp`](surfsense_mcp) | MCP server over the REST API |
| [`docker`](docker) | Compose files, the sandbox image and the install scripts |

## License

[Apache 2.0](LICENSE), except [`surfsense_backend/app/proprietary/`](surfsense_backend/app/proprietary), which is under the Business Source License 1.1.
