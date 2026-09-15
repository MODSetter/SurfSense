FROM keygen/api:v1.7.2

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/v1/health || exit 1
