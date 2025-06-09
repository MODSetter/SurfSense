# ---------- image names ----------
OWNER          ?= erauner12
SHORT_SHA      := $(shell git rev-parse --short HEAD)

BACKEND_IMAGE  := ghcr.io/$(OWNER)/surfsense_backend
UI_IMAGE       := ghcr.io/$(OWNER)/surfsense_ui

# ---------- Buildx target ----------
define buildx =
	docker buildx build \
		--builder multi \      # configurable: see docs/build.md
		--pull \
		--platform linux/amd64,linux/arm64 \
		-f $1/Dockerfile \
		-t $2:$(SHORT_SHA) \
		--push \
		$1
endef

.PHONY: backend-image ui-image

backend-image:
	$(call buildx,surfsense_backend,$(BACKEND_IMAGE))

ui-image:
	$(call buildx,surfsense_web,$(UI_IMAGE))