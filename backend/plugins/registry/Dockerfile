# syntax=docker.io/docker/dockerfile:1
# The registry container, beside the plugin host at plugins.surfsense.com.
#   docker build -t surfsense-registry backend/plugins/registry
#   docker run -p 8080:8080 surfsense-registry
# published/ holds what CI signed on main; until then the image serves no list.

# 2.11.4, released 3 Jun 2026.
FROM caddy:2.11.4-alpine@sha256:6aeddd44c3078b0f9a35206472a11420648a79c184603ef95957d0a20044cb2b

ENV PORT=8080

COPY Caddyfile /etc/caddy/Caddyfile
WORKDIR /srv/registry
COPY published/ published/
COPY icons/ icons/
COPY oauth/client.json oauth/callback.html oauth/

RUN adduser -D -H -u 10001 registry && chown -R registry /config /data
USER registry

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
    CMD wget -q -O /dev/null "http://127.0.0.1:${PORT}/health" || exit 1
