# Building & Publishing SurfSense Docker Images

> **TL;DR**
> ```bash
> # one-time
> docker buildx create --use --name multi
>
> # backend
> make backend-image
>
> # UI
> make ui-image
> ```

## 1. Prerequisites
* Docker ≥ 24.0 with BuildKit
* `buildx` plugin (ships with Docker Desktop and docker-ce on Linux)
* GHCR write access (`echo $CR_PAT | docker login ghcr.io -u <user> --password-stdin`)

## 2. Clearing a poisoned APT cache
If you ever see
`E: Could not get lock /var/cache/apt/archives/lock`
run
```bash
docker buildx prune --builder multi --filter type=cache --force
```

## 3. Full commands (copy-paste)
```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -f surfsense_backend/Dockerfile \
  -t ghcr.io/erauner12/surfsense_backend:latest \
  -t ghcr.io/erauner12/surfsense_backend:$(git rev-parse --short HEAD) \
  --push surfsense_backend
# …same pattern for surfsense_web…
```


---


# 0) authenticate once per shell

```
echo "$CR_PAT" | docker login ghcr.io -u erauner12 --password-stdin
docker buildx create --use --name multi 2>/dev/null || docker buildx use multi

SHA=$(git rev-parse --short HEAD)
```

# ─── UI ─────────────────────────────────────────────

```
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f surfsense_web/Dockerfile \
  -t ghcr.io/erauner12/surfsense_ui:latest \
  -t ghcr.io/erauner12/surfsense_ui:$SHA \
  --push \
  surfsense_web
```

# ─── Backend ────────────────────────────────────────
```
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f surfsense_backend/Dockerfile \
  -t ghcr.io/erauner12/surfsense_backend:latest \
  -t ghcr.io/erauner12/surfsense_backend:$SHA \
  --push \
  surfsense_backend
```
